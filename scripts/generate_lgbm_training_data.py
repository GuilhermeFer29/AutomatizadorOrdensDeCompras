"""Gera conjunto sintético rico para treinar o modelo global LightGBM."""

from __future__ import annotations

import argparse
import logging
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable, List

import numpy as np
from sqlmodel import Session

from app.core.database import engine
from app.models.models import PrecosHistoricos, Produto

LOGGER = logging.getLogger(__name__)
DEFAULT_DAYS = 365 * 2
DEFAULT_PRODUCTS = 20


def _date_range(days: int) -> Iterable[datetime]:
    today = datetime.now(timezone.utc).date()
    start = today - timedelta(days=days - 1)
    for offset in range(days):
        yield datetime.combine(start + timedelta(days=offset), datetime.min.time(), tzinfo=timezone.utc)


def _seasonality_factor(day_index: int, category_factor: float) -> float:
    weekly = 1 + 0.15 * np.sin(2 * np.pi * (day_index % 7) / 7)
    yearly = 1 + 0.25 * np.sin(2 * np.pi * day_index / 365)
    return weekly * yearly * category_factor


def _generate_price_series(base_price: float, noise_scale: float, days: int, category_factor: float) -> List[float]:
    prices: List[float] = []
    for i in range(days):
        trend = 1 + 0.0005 * i
        seasonal = _seasonality_factor(i, category_factor)
        noise = np.random.normal(0, noise_scale)
        value = base_price * trend * seasonal + noise
        prices.append(max(value, base_price * 0.4))
    return prices


def _ensure_products(total_products: int) -> List[Produto]:
    produtos: List[Produto] = []
    with Session(engine) as session:
        count = session.query(Produto).count()
        if count >= total_products:
            produtos = list(session.exec(Produto.select()).limit(total_products))
            return produtos

        LOGGER.info("Criando %s produtos fictícios", total_products - count)
        for idx in range(total_products - count):
            produto = Produto(
                nome=f"Produto Sintético {count + idx + 1}",
                sku=f"SYN-{count + idx + 1:04d}",
                categoria=random.choice(["metal", "polímero", "eletrônico", "embalagem"]),
                estoque_atual=random.randint(20, 200),
                estoque_minimo=random.randint(5, 30),
            )
            session.add(produto)
        session.commit()
        produtos = list(session.exec(Produto.select()).limit(total_products))
    return produtos


def generate_dataset(total_products: int, days: int) -> None:
    produtos = _ensure_products(total_products)

    registros: List[PrecosHistoricos] = []
    categories = {"metal": 1.05, "polímero": 0.95, "eletrônico": 1.15, "embalagem": 0.9}

    for produto in produtos:
        base_price = random.uniform(50, 450)
        noise_scale = random.uniform(1.5, 12)
        category_factor = categories.get(produto.categoria or "metal", 1.0)
        prices = _generate_price_series(base_price, noise_scale, days, category_factor)

        for day_index, (timestamp, price) in enumerate(zip(_date_range(days), prices)):
            registros.append(
                PrecosHistoricos(
                    produto_id=produto.id,
                    fornecedor="Fornecedor Sintético",
                    preco=price,
                    moeda="BRL",
                    coletado_em=timestamp,
                    is_synthetic=True,
                )
            )

    with Session(engine) as session:
        session.exec(PrecosHistoricos.delete().where(PrecosHistoricos.is_synthetic == True))  # noqa: E712
        session.bulk_save_objects(registros)
        session.commit()

    LOGGER.info(
        "Dados sintéticos gerados: %s produtos, %s dias (%s registros).",
        len(produtos),
        days,
        len(registros),
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Gera histórico sintético para treinamento LightGBM.")
    parser.add_argument("--products", type=int, default=DEFAULT_PRODUCTS, help="Quantidade de produtos")
    parser.add_argument("--days", type=int, default=DEFAULT_DAYS, help="Quantidade de dias históricos")
    parser.add_argument("--skip-dotenv", action="store_true", help="Não carregar variáveis do .env")
    return parser.parse_args()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s:%(message)s")
    args = parse_args()

    if not args.skip_dotenv:
        from dotenv import load_dotenv

        load_dotenv()

    generate_dataset(total_products=args.products, days=args.days)


if __name__ == "__main__":
    main()
