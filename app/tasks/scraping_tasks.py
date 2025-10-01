"""Celery tasks responsible for orchestrating scraping jobs."""

from __future__ import annotations

from typing import Any, Dict, List

import structlog
from celery import shared_task
from sqlmodel import Session, select

from app.core.database import engine
from app.models.models import Produto
from app.services.scraping_service import ScrapingOutcome, scrape_and_save_price

LOGGER = structlog.get_logger(__name__)


@shared_task(name="app.tasks.scraping.scrape_product")
def scrape_product(produto_id: int) -> Dict[str, Any]:
    """Collect and persist the price for a specific product."""

    LOGGER.info("Iniciando scraping de produto", produto_id=produto_id)
    outcome = scrape_and_save_price(produto_id)

    return {
        "produto_id": outcome.produto_id,
        "price": str(outcome.price),
        "currency": outcome.currency,
        "source": outcome.source,
        "fallback": outcome.used_fallback,
    }


@shared_task(name="app.tasks.scraping.scrape_all_products")
def scrape_all_products() -> List[Dict[str, Any]]:
    """Collect prices for all products registered in the database."""

    resultados: List[Dict[str, Any]] = []
    with Session(engine) as session:
        produtos = session.exec(select(Produto)).all()

    for produto in produtos:
        try:
            LOGGER.info("Processando produto para scraping", produto_id=produto.id, sku=produto.sku)
            outcome: ScrapingOutcome = scrape_and_save_price(produto.id)
            resultados.append(
                {
                    "produto_id": outcome.produto_id,
                    "price": str(outcome.price),
                    "currency": outcome.currency,
                    "source": outcome.source,
                    "fallback": outcome.used_fallback,
                }
            )
        except Exception as error:  # noqa: BLE001
            LOGGER.error(
                "Falha ao coletar preço do produto",
                produto_id=produto.id,
                sku=produto.sku,
                error=str(error),
            )

    return resultados
