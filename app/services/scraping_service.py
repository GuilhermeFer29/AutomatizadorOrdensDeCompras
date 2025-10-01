"""Service layer responsible for orchestrating price scraping workflows."""

from __future__ import annotations

import os
import random
import re
from urllib.parse import quote_plus
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

import structlog
from sqlmodel import Session, select

from app.core.database import engine
from app.models.models import PrecosHistoricos, Produto
from app.scraping.scrapers import (
    ScrapeResult,
    ScrapeSpec,
    ScrapingError,
    build_proxy_configuration_from_env,
    scrape_price,
)

LOGGER = structlog.get_logger(__name__)


@dataclass(slots=True)
class ScrapingOutcome:
    """Simple data container describing the scraping execution."""

    produto_id: int
    price: Decimal
    currency: str
    source: str
    used_fallback: bool = False


def scrape_and_save_price(produto_id: int) -> ScrapingOutcome:
    """Fetch the current price for ``produto_id`` and persist it in the database."""

    with Session(engine) as session:
        produto = session.get(Produto, produto_id)
        if produto is None:
            raise ValueError(f"Produto com ID {produto_id} não encontrado.")

        spec = _build_spec_for_product(produto)
        proxies = build_proxy_configuration_from_env()

        try:
            result = scrape_price(spec, proxies=proxies or None)
            used_fallback = result.source != "playwright"
        except ScrapingError as error:
            if not _allow_fake_data():
                LOGGER.error(
                    "Falha no scraping",
                    produto_id=produto.id,
                    sku=produto.sku,
                    url=spec.url,
                    error=str(error),
                )
                raise

            result = _generate_mock_result(produto)
            used_fallback = True
            LOGGER.warning(
                "Usando preço simulado após falha de scraping",
                produto_id=produto.id,
                sku=produto.sku,
                url=spec.url,
                error=str(error),
            )

        _persist_price(session=session, produto=produto, result=result)
        session.commit()

        LOGGER.info(
            "Preço coletado com sucesso",
            produto_id=produto.id,
            sku=produto.sku,
            preco=str(result.price),
            moeda=result.currency,
            source=result.source,
            fallback=used_fallback,
        )

        return ScrapingOutcome(
            produto_id=produto.id,
            price=result.price,
            currency=result.currency,
            source=result.source,
            used_fallback=used_fallback,
        )


def _build_spec_for_product(produto: Produto) -> ScrapeSpec:
    base_url_template = os.getenv("SCRAPING_BASE_URL", "https://example.com/produtos/{sku}")
    nome_slug = _slugify(produto.nome or produto.sku)
    query = quote_plus(produto.nome or produto.sku)

    try:
        url = base_url_template.format(sku=produto.sku, nome_slug=nome_slug, query=query)
    except KeyError:
        url = base_url_template

    selector = os.getenv("SCRAPING_PRICE_SELECTOR", ".price")
    currency = os.getenv("SCRAPING_CURRENCY", "BRL")

    return ScrapeSpec(
        url=url,
        price_selector=selector,
        currency=currency,
        metadata={
            "produto_id": produto.id,
            "sku": produto.sku,
            "nome": produto.nome,
            "categoria": produto.categoria,
        },
    )


def _allow_fake_data() -> bool:
    return os.getenv("SCRAPING_ALLOW_FAKE_DATA", "false").lower() in {"1", "true", "yes"}


def _generate_mock_result(produto: Produto) -> ScrapeResult:
    minimum = Decimal(os.getenv("SCRAPING_MOCK_PRICE_MIN", "80.0"))
    maximum = Decimal(os.getenv("SCRAPING_MOCK_PRICE_MAX", "150.0"))
    if maximum < minimum:
        maximum = minimum

    fraction = Decimal(str(random.random())) if maximum > minimum else Decimal("0")
    price = minimum + (maximum - minimum) * fraction
    return ScrapeResult(
        price=price.quantize(Decimal("0.01")),
        currency=os.getenv("SCRAPING_CURRENCY", "BRL"),
        raw_text=str(price),
        source="mock",
        metadata={"produto_id": produto.id, "sku": produto.sku, "nome": produto.nome},
    )


def _persist_price(*, session: Session, produto: Produto, result: ScrapeResult) -> None:
    latest_price = session.exec(
        select(PrecosHistoricos)
        .where(PrecosHistoricos.produto_id == produto.id)
        .order_by(PrecosHistoricos.coletado_em.desc())
    ).first()

    now = datetime.now(timezone.utc)
    if _should_skip_price_update(latest_price, result.price, now):
        LOGGER.info(
            "Preço não alterado, ignorando atualização",
            produto_id=produto.id,
            preco=str(result.price),
        )
        return

    registro = PrecosHistoricos(
        produto_id=produto.id,
        fornecedor=(result.metadata or {}).get("fornecedor", "scraper"),
        preco=result.price,
        moeda=result.currency,
        coletado_em=now,
    )
    session.add(registro)


def _should_skip_price_update(latest_price: Optional[PrecosHistoricos], new_price: Decimal, current_time: datetime) -> bool:
    """Determine if price update should be skipped based on latest price and timing."""
    if latest_price is None:
        return False
    
    # Skip if price hasn't changed
    if latest_price.preco == new_price:
        return True
    
    return False


def _slugify(texto: str) -> str:
    sanitized = re.sub(r"\s+", "-", texto.strip().lower())
    sanitized = re.sub(r"[^a-z0-9-]", "", sanitized)
    return sanitized or "produto"


__all__ = ["ScrapingOutcome", "scrape_and_save_price"]
