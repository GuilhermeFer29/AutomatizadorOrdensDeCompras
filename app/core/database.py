"""Database engine and session management utilities."""

from __future__ import annotations

import os
import logging
import time
from typing import Generator

from sqlalchemy.engine import Engine
from sqlalchemy.exc import OperationalError
from sqlmodel import Session, SQLModel, create_engine

DEFAULT_DATABASE_URL = "mysql+mysqlconnector://app_user:app_password@db:3306/app_db"

LOGGER = logging.getLogger(__name__)


def _get_database_url() -> str:
    """Read the database URL from the environment, falling back to defaults."""
    database_url = os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL)
    if not database_url:
        raise RuntimeError("DATABASE_URL environment variable must be configured")
    return database_url


def create_engine_instance() -> Engine:
    """Instantiate the SQLModel engine for the configured database."""
    return create_engine(
        _get_database_url(),
        echo=False,
        pool_pre_ping=True,
    )


engine: Engine = create_engine_instance()


def create_db_and_tables() -> None:
    """Create database tables with retry logic"""
    max_retries = 5
    retry_delay = 2

    for attempt in range(max_retries):
        try:
            SQLModel.metadata.create_all(engine)
            LOGGER.info("Database tables created successfully")
            return
        except OperationalError as e:
            if attempt < max_retries - 1:
                LOGGER.warning(
                    "Database connection failed (attempt %d/%d). Retrying in %ds...",
                    attempt + 1,
                    max_retries,
                    retry_delay,
                )
                time.sleep(retry_delay)
                retry_delay *= 2  # Exponential backoff
            else:
                LOGGER.error("Failed to connect to database after %d attempts", max_retries)
                raise e


def get_session() -> Generator[Session, None, None]:
    """Provide a session generator compatible with FastAPI dependencies."""
    with Session(engine) as session:
        yield session


__all__ = ["engine", "get_session", "create_db_and_tables", "wait_for_database"]
