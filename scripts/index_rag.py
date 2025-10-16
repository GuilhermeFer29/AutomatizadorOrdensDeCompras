"""Script para indexar produtos no RAG (ChromaDB)."""

from __future__ import annotations
import sys
import logging
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv
from sqlmodel import Session
from app.core.database import engine
from app.services.rag_service import index_product_catalog

LOGGER = logging.getLogger(__name__)


def main():
    """Indexa o catálogo de produtos no vector store."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s:%(message)s")
    load_dotenv()
    
    LOGGER.info("🔍 Iniciando indexação do catálogo de produtos no RAG...")
    
    with Session(engine) as session:
        try:
            index_product_catalog(session)
            LOGGER.info("✅ Indexação concluída com sucesso!")
        except Exception as e:
            LOGGER.error(f"❌ Erro na indexação: {e}")
            raise


if __name__ == "__main__":
    main()
