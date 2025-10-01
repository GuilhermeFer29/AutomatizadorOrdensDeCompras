"""Service orchestrating Mercado Livre scraping and persistence."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from decimal import Decimal

import structlog
from sqlmodel import Session

from app.core.database import engine
from app.models.models import PrecosHistoricos, Produto
from app.scraping.scrapers import scrape_mercadolivre

LOGGER = structlog.get_logger(__name__)
DEFAULT_CURRENCY = os.getenv("SCRAPING_CURRENCY", "BRL")


def scrape_and_save_price(produto_id: int) -> None:
    """Scrape Mercado Livre for ``produto_id`` and persist the price."""

    LOGGER.info("Iniciando scraping de preço", produto_id=produto_id)

    with Session(engine) as session:
        produto = session.get(Produto, produto_id)
        if produto is None:
            LOGGER.warning("Produto não encontrado para scraping", produto_id=produto_id)
            return

        termo_busca = produto.nome or produto.sku
        if not termo_busca:
            LOGGER.warning(
                "Produto não possui nome ou SKU para consulta",
                produto_id=produto.id,
            )
            return

        preco = scrape_mercadolivre(termo_busca)
        if preco is None:
            LOGGER.warning(
                "Scraping não retornou preço",
                produto_id=produto.id,
                termo_busca=termo_busca,
            )
            return

        preco_decimal = Decimal(str(preco)).quantize(Decimal("0.01"))
        registro = PrecosHistoricos(
            produto_id=produto.id,
            fornecedor="mercado_livre",
            preco=preco_decimal,
            moeda=DEFAULT_CURRENCY,
            coletado_em=datetime.now(timezone.utc),
        )
        session.add(registro)
        session.commit()

        LOGGER.info(
            "Preço salvo com sucesso",
            produto_id=produto.id,
            preco=str(preco_decimal),
            moeda=DEFAULT_CURRENCY,
        )


__all__ = ["scrape_and_save_price"]
