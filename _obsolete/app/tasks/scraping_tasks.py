"""Tarefas Celery para scraping de preços no Mercado Livre."""

from __future__ import annotations

import structlog
from celery import shared_task
from sqlmodel import Session, select

from app.core.database import engine
from app.models.models import Produto
from app.services.scraping_service import scrape_and_save_price

LOGGER = structlog.get_logger(__name__)


@shared_task(name="app.tasks.scraping.scrape_product")
def scrape_product(produto_id: int) -> None:
    """Executa o scraping e persiste o preço de um único produto."""

    LOGGER.info("Disparando scraping individual", produto_id=produto_id)
    scrape_and_save_price(produto_id)


@shared_task(name="app.tasks.scraping.scrape_all_products")
def scrape_all_products() -> None:
    """Realiza scraping para todos os produtos cadastrados."""

    with Session(engine) as session:
        produtos = session.exec(select(Produto)).all()

    LOGGER.info("Iniciando scraping em lote", total_produtos=len(produtos))

    for produto in produtos:
        try:
            scrape_and_save_price(produto.id)
        except Exception as error:  # noqa: BLE001
            LOGGER.error(
                "Erro ao executar scraping do produto",
                produto_id=produto.id,
                sku=produto.sku,
                error=str(error),
            )

    LOGGER.info("Scraping em lote concluído", total_processados=len(produtos))
