"""Utility script to reset the relational database schema from scratch."""

from __future__ import annotations

import logging
from pathlib import Path
import sys

from dotenv import load_dotenv
from sqlmodel import SQLModel

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.core.database import create_db_and_tables, engine

LOGGER = logging.getLogger(__name__)


def configure_logging() -> None:
    """Configure basic logging for CLI execution."""

    logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s:%(message)s")


def reset_schema() -> None:
    """Drop every SQLModel-managed table and recreate the schema."""

    LOGGER.info("Dropping existing schema")
    SQLModel.metadata.drop_all(engine)
    LOGGER.info("Creating tables from metadata")
    create_db_and_tables()
    LOGGER.info("Database schema recreated with success")


def main() -> None:
    """CLI entry point."""

    load_dotenv()
    configure_logging()
    reset_schema()


if __name__ == "__main__":
    main()
