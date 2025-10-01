"""Seed synthetic price history for all products to support model training."""

from __future__ import annotations

import argparse
import logging
import math
import random
import sys
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

from dotenv import load_dotenv
from sqlmodel import Session, delete, select

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.core.database import engine
from app.models.models import PrecosHistoricos, Produto

LOGGER = logging.getLogger(__name__)


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Populate synthetic price history for all products.")
    parser.add_argument("--truncate", action="store_true", help="Remove existing price history before seeding.")
    parser.add_argument(
        "--points",
        type=int,
        default=14,
        help="Number of historical points to create per product (default: 14).",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=20241001,
        help="Random seed used to generate price fluctuations.",
    )
    return parser.parse_args()


def configure_logging() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s:%(message)s")


def _base_price_for_product(produto: Produto) -> float:
    hash_source = f"{produto.id}-{produto.sku}-{produto.nome}".encode("utf-8", "ignore")
    deterministic = sum(byte for byte in hash_source) % 400
    return 80.0 + deterministic


def _calculate_price(base_price: float, step: int, rng: random.Random) -> Decimal:
    trend = 1 + 0.01 * math.sin(step / 3)
    noise = rng.uniform(-0.05, 0.05)
    value = max(base_price * trend * (1 + noise), 15.0)
    return Decimal(f"{value:.2f}")


def seed_price_history(truncate: bool, points: int, seed: int) -> None:
    if points < 5:
        raise ValueError("É necessário gerar pelo menos 5 pontos históricos para treinar o modelo.")

    rng = random.Random(seed)
    now = datetime.now(timezone.utc)

    with Session(engine) as session:
        produtos = session.exec(select(Produto)).all()
        if not produtos:
            LOGGER.warning("Nenhum produto cadastrado para geração de histórico.")
            return

        if truncate:
            LOGGER.info("Removendo histórico de preços existente.")
            session.exec(delete(PrecosHistoricos))
            session.commit()

        LOGGER.info("Gerando histórico sintético", total_produtos=len(produtos), pontos=points)
        registros_criados = 0

        for produto in produtos:
            base_price = _base_price_for_product(produto)
            for step in range(points):
                coleta_em = now - timedelta(days=points - step)
                preco = _calculate_price(base_price, step, rng)

                existente = session.exec(
                    select(PrecosHistoricos)
                    .where(PrecosHistoricos.produto_id == produto.id)
                    .where(PrecosHistoricos.coletado_em == coleta_em)
                ).first()
                if existente:
                    existente.preco = preco
                    continue

                session.add(
                    PrecosHistoricos(
                        produto_id=produto.id,
                        fornecedor="sintetico",
                        preco=preco,
                        moeda="BRL",
                        coletado_em=coleta_em,
                    )
                )
                registros_criados += 1

        session.commit()

    LOGGER.info("Histórico sintético concluído", registros=registros_criados)


def main() -> None:
    load_dotenv()
    configure_logging()
    args = parse_arguments()
    seed_price_history(truncate=args.truncate, points=args.points, seed=args.seed)


if __name__ == "__main__":
    main()
