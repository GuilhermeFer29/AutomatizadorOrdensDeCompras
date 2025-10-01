"""Database engine and session management utilities."""

from __future__ import annotations

import os
import logging
from typing import Generator

from sqlalchemy.engine import Engine
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
    """Ensure database schema is created for all SQLModel tables."""
    # Import models at runtime to guarantee they are registered with SQLModel's metadata
    from app.models import models  # noqa: F401  # pylint: disable=unused-import

    SQLModel.metadata.create_all(engine)
    LOGGER.info("Database schema ensured via SQLModel metadata")


def get_session() -> Generator[Session, None, None]:
    """Provide a session generator compatible with FastAPI dependencies."""
    with Session(engine) as session:
        yield session
