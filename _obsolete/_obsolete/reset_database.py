"""Utility script to reset the relational database schema from scratch."""

from __future__ import annotations

import logging
from pathlib import Path
import sys

from dotenv import load_dotenv
from sqlmodel import Session, SQLModel

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


def reset_database() -> None:
    """Remove todas as tabelas e recria estrutura vazia."""
    try:
        LOGGER.info("🗑️  Iniciando limpeza do banco de dados...")
        
        # Drop todas as tabelas
        SQLModel.metadata.drop_all(engine)
        LOGGER.info("✅ Tabelas removidas com sucesso")
        
        # Recria estrutura vazia
        SQLModel.metadata.create_all(engine)
        LOGGER.info("✅ Estrutura do banco recriada")
        
        # Verifica tabelas criadas
        with Session(engine) as session:
            from sqlalchemy import text
            result = session.exec(text("SHOW TABLES"))
            tables = [row[0] for row in result]
            LOGGER.info(f"📋 Tabelas disponíveis: {tables}")
        
        LOGGER.info("🎉 Reset do banco de dados concluído!")
        
    except Exception as e:
        LOGGER.error(f"❌ Erro ao resetar banco: {e}")
        raise


def main() -> None:
    """CLI entry point."""

    load_dotenv()
    configure_logging()
    reset_database()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Reseta o banco de dados (DROP + CREATE)")
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="Confirma a operação de reset (OBRIGATÓRIO para segurança)"
    )
    
    args = parser.parse_args()
    
    if not args.confirm:
        LOGGER.error("❌ Operação cancelada. Use --confirm para prosseguir.")
        LOGGER.warning("⚠️  ATENÇÃO: Esta operação APAGARÁ TODOS OS DADOS!")
        sys.exit(1)
    
    LOGGER.warning("⚠️  ATENÇÃO: Você está prestes a APAGAR TODOS OS DADOS!")
    LOGGER.warning("⚠️  Pressione Ctrl+C nos próximos 5 segundos para cancelar...")
    
    import time
    for i in range(5, 0, -1):
        LOGGER.warning(f"⏳ {i}...")
        time.sleep(1)
    
    main()
