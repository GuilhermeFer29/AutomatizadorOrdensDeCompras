"""Execute bulk scraping for the entire catalogue using ScraperAPI."""

from __future__ import annotations

import argparse
import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Iterable, List, Sequence

# Ajuste para permitir a importação do pacote ``app`` ao executar a partir de scripts/
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from sqlmodel import Session, select

from app.core.database import engine
from app.models.models import Produto
from app.services.scraping_service import ScrapingOutcome, scrape_and_save_price

LOGGER = logging.getLogger("bulk_scraping")


@dataclass(slots=True)
class ScrapeSummary:
    """Accumulate statistics for the bulk scraping run."""

    success: int = 0
    failure: int = 0
    attempts: int = 0

    def register_success(self) -> None:
        self.success += 1
        self.attempts += 1

    def register_failure(self) -> None:
        self.failure += 1
        self.attempts += 1


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Bulk scrape prices for products using ScraperAPI.")
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Number of products to scrape (default: all products).",
    )
    parser.add_argument(
        "--rounds",
        type=int,
        default=1,
        help="How many passes to execute over the selected products.",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=3,
        help="Number of parallel worker threads (max recommended: 5).",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=1.0,
        help="Seconds to wait between each wave of requests to respect rate limits.",
    )
    parser.add_argument(
        "--shuffle",
        action="store_true",
        help="Randomize the product order before scraping.",
    )
    return parser.parse_args()


def chunked(sequence: Sequence[int], size: int) -> Iterable[Sequence[int]]:
    for index in range(0, len(sequence), size):
        yield sequence[index : index + size]


def load_product_ids(limit: int | None = None, shuffle: bool = False) -> List[int]:
    with Session(engine) as session:
        statement = select(Produto.id).order_by(Produto.id)
        product_ids = session.exec(statement).all()

    if shuffle:
        import random

        random.shuffle(product_ids)

    if limit is not None:
        product_ids = product_ids[:limit]

    return product_ids


def scrape_product(produto_id: int) -> ScrapingOutcome:
    start = time.perf_counter()
    outcome = scrape_and_save_price(produto_id)
    duration = time.perf_counter() - start
    LOGGER.info(
        "Preço coletado",
        extra={
            "produto_id": produto_id,
            "preco": str(outcome.price),
            "moeda": outcome.currency,
            "source": outcome.source,
            "duracao": round(duration, 2),
        },
    )
    return outcome


def execute_wave(product_ids: Sequence[int], max_workers: int) -> ScrapeSummary:
    summary = ScrapeSummary()

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_map = {executor.submit(scrape_product, produto_id): produto_id for produto_id in product_ids}

        for future in as_completed(future_map):
            produto_id = future_map[future]
            try:
                future.result()
                summary.register_success()
            except Exception as exc:  # noqa: BLE001
                summary.register_failure()
                LOGGER.error("Falha no scraping", extra={"produto_id": produto_id, "erro": str(exc)})

    return summary


def run_bulk_scraping(product_ids: Sequence[int], rounds: int, concurrency: int, delay: float) -> ScrapeSummary:
    total_summary = ScrapeSummary()

    for round_number in range(1, rounds + 1):
        LOGGER.info("Iniciando rodada", extra={"rodada": round_number})
        for batch in chunked(product_ids, concurrency):
            summary = execute_wave(batch, max_workers=len(batch))
            total_summary.success += summary.success
            total_summary.failure += summary.failure
            total_summary.attempts += summary.attempts
            if delay:
                time.sleep(delay)

    return total_summary


def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )


def main() -> None:
    args = parse_arguments()
    configure_logging()

    if args.concurrency < 1:
        raise ValueError("Concurrency deve ser pelo menos 1.")
    if args.concurrency > 5:
        LOGGER.warning("Reducing concurrency to 5 to comply with ScraperAPI limits.")
        args.concurrency = 5

    product_ids = load_product_ids(limit=args.limit, shuffle=args.shuffle)
    if not product_ids:
        LOGGER.warning("Nenhum produto encontrado para scraping.")
        return

    LOGGER.info(
        "Iniciando scraping em lote",
        extra={
            "produtos": len(product_ids),
            "rodadas": args.rounds,
            "concurrency": args.concurrency,
        },
    )

    summary = run_bulk_scraping(
        product_ids=product_ids,
        rounds=args.rounds,
        concurrency=args.concurrency,
        delay=args.delay,
    )

    sucesso_percentual = (summary.success / summary.attempts * 100.0) if summary.attempts else 0.0
    LOGGER.info(
        "Resumo do scraping",
        extra={
            "tentativas": summary.attempts,
            "sucessos": summary.success,
            "falhas": summary.failure,
            "sucesso_percentual": round(sucesso_percentual, 2),
        },
    )


if __name__ == "__main__":
    main()
