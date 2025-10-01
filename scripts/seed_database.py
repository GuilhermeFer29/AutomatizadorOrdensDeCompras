"""Seed the database with historical sales data from a CSV file."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services.sales_ingestion_service import ingest_sales_dataframe, load_sales_dataframe

LOGGER = logging.getLogger(__name__)


def parse_arguments() -> argparse.Namespace:
    """Build and parse command-line arguments."""

    parser = argparse.ArgumentParser(description="Seed the MySQL database with sales history data.")
    parser.add_argument("csv_path", type=Path, help="Path to the CSV file containing sales records.")
    return parser.parse_args()


def configure_logging() -> None:
    """Configure a basic logging handler for CLI execution."""

    logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s:%(message)s")


def main() -> None:
    """Entry point for the seeding script."""

    configure_logging()
    load_dotenv()

    args = parse_arguments()
    if not args.csv_path.is_file():
        raise FileNotFoundError(f"Arquivo CSV não encontrado: {args.csv_path}")

    with args.csv_path.open("rb") as file_handle:
        dataframe = load_sales_dataframe(file_handle)

    produtos = ingest_sales_dataframe(dataframe=dataframe)
    LOGGER.info("Seed finalizado. Produtos atualizados: %s", produtos)


if __name__ == "__main__":
    main()
