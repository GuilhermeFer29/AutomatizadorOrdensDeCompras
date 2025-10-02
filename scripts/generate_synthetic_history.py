import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parents[1]))

from __future__ import annotations

import argparse
import math
import random
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Iterable, List, Tuple

import structlog
from sqlmodel import Session, delete, select

from app.core.database import engine
from app.models.models import PrecosHistoricos, Produto

LOGGER = structlog.get_logger(__name__)

SYNTHETIC_SUPPLIER = "histórico sintético"
DEFAULT_MONTHS = 6
MAX_RANDOM_VARIATION = 0.10
SAZONALIDADE_FREQUENCIA_DIAS = 30
WEEKEND_DISCOUNT = 0.97
PROMOTION_BONUS = 1.04


def _quantize_price(value: float) -> Decimal:
    """Round the generated price to four decimal places using bankers rounding."""

    return Decimal(str(value)).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)


def _remove_existing_synthetic_history(session: Session) -> int:
    """Delete previously generated synthetic history entries and return the affected rows."""

    result = session.exec(delete(PrecosHistoricos).where(PrecosHistoricos.is_synthetic == True))  # noqa: PLR2004
    session.commit()
    return result.rowcount if result is not None else 0


def _fetch_products(session: Session) -> List[Produto]:
    """Return the complete list of products available in the catalogue."""

    return list(session.exec(select(Produto).order_by(Produto.nome)))


def _fetch_last_real_observation(session: Session, produto_id: int) -> PrecosHistoricos | None:
    """Fetch the most recent real price observation for the provided product."""

    return session.exec(
        select(PrecosHistoricos)
        .where(PrecosHistoricos.produto_id == produto_id)
        .where(PrecosHistoricos.is_synthetic == False)  # noqa: PLR2004
        .order_by(PrecosHistoricos.coletado_em.desc())
        .limit(1)
    ).first()


def _existing_synthetic_dates(session: Session, produto_id: int) -> Iterable[datetime]:
    """Return the datetime values already marked as synthetic to avoid duplicates."""

    registros = session.exec(
        select(PrecosHistoricos.coletado_em)
        .where(PrecosHistoricos.produto_id == produto_id)
        .where(PrecosHistoricos.is_synthetic == True)  # noqa: PLR2004
    )
    return [registro.replace(tzinfo=timezone.utc) for registro in registros]


def _seasonal_factor(day_index: int) -> float:
    """Calculate a smooth seasonal oscillation for the informed day index."""

    radians = (2 * math.pi * day_index) / SAZONALIDADE_FREQUENCIA_DIAS
    return 1 + 0.05 * math.sin(radians)


def _weekend_adjustment(target_date: datetime) -> float:
    """Return a small discount for weekend dates to simulate lower demand."""

    return WEEKEND_DISCOUNT if target_date.weekday() >= 5 else 1.0


def _promotion_adjustment(target_date: datetime) -> float:
    """Model periodic promotion spikes at the beginning of each month."""

    return PROMOTION_BONUS if target_date.day <= 3 else 1.0


def _generate_price_series(
    *,
    base_price: Decimal,
    start_date: datetime,
    days: int,
    existing_datetimes: Iterable[datetime],
) -> List[Tuple[datetime, Decimal]]:
    """Generate a sequence of synthetic price points for the informed range."""

    synthetic_points: List[Tuple[datetime, Decimal]] = []
    current_price = float(base_price)
    occupied = {item.date() for item in existing_datetimes}

    for offset in range(1, days + 1):
        target_date = start_date - timedelta(days=offset)
        if target_date.date() in occupied:
            continue

        random_factor = random.uniform(1 - MAX_RANDOM_VARIATION, 1 + MAX_RANDOM_VARIATION)
        seasonal_factor = _seasonal_factor(offset)
        weekend_factor = _weekend_adjustment(target_date)
        promotion_factor = _promotion_adjustment(target_date)

        adjusted_price = max(0.01, current_price * random_factor * seasonal_factor * weekend_factor * promotion_factor)
        quantized_price = _quantize_price(adjusted_price)
        current_price = float(quantized_price)

        synthetic_points.append((target_date, quantized_price))

    return list(reversed(synthetic_points))


def _create_synthetic_entry(
    *, produto_id: int, fornecedor: str | None, moeda: str, preco: Decimal, coletado_em: datetime
) -> PrecosHistoricos:
    """Instantiate a synthetic price record ready to be persisted."""

    return PrecosHistoricos(
        produto_id=produto_id,
        fornecedor=fornecedor or SYNTHETIC_SUPPLIER,
        preco=preco,
        moeda=moeda,
        coletado_em=coletado_em.replace(tzinfo=timezone.utc),
        is_synthetic=True,
    )


def generate_synthetic_history(months: int = DEFAULT_MONTHS) -> None:
    """Populate the database with synthetic price points for each product."""

    LOGGER.info("synthetic.history.start", meses=months)
    days = months * 30

    with Session(engine) as session:
        removed = _remove_existing_synthetic_history(session)
        if removed:
            LOGGER.info("synthetic.history.cleanup", registros_removidos=removed)

        produtos = _fetch_products(session)
        if not produtos:
            LOGGER.warning("synthetic.history.no_products")
            return

        now_utc = datetime.now(timezone.utc)
        registros_inseridos = 0

        for produto in produtos:
            ultimo_real = _fetch_last_real_observation(session, produto.id)
            if ultimo_real is None:
                LOGGER.warning(
                    "synthetic.history.skip.sem_dados_reais",
                    produto_id=produto.id,
                    produto_nome=produto.nome,
                )
                continue

            existentes = _existing_synthetic_dates(session, produto.id)
            series = _generate_price_series(
                base_price=ultimo_real.preco,
                start_date=now_utc,
                days=days,
                existing_datetimes=existentes,
            )

            entradas = [
                _create_synthetic_entry(
                    produto_id=produto.id,
                    fornecedor=ultimo_real.fornecedor,
                    moeda=ultimo_real.moeda,
                    preco=preco,
                    coletado_em=timestamp,
                )
                for timestamp, preco in series
            ]

            session.add_all(entradas)
            session.commit()
            registros_inseridos += len(entradas)

            LOGGER.info(
                "synthetic.history.produto",
                produto_id=produto.id,
                produto_nome=produto.nome,
                registros=len(entradas),
                preco_base=float(ultimo_real.preco),
            )

        LOGGER.info("synthetic.history.completed", registros_inseridos=registros_inseridos)


def _parse_args() -> argparse.Namespace:
    """Parse CLI arguments for the synthetic history generator."""

    parser = argparse.ArgumentParser(description="Gera histórico sintético retroativo para todos os produtos.")
    parser.add_argument(
        "--months",
        type=int,
        default=DEFAULT_MONTHS,
        help="Quantidade de meses retroativos a serem gerados (padrão: 6).",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    random.seed()
    generate_synthetic_history(months=max(1, args.months))
