
import sys
import os
from pathlib import Path

# Adiciona raiz do projeto ao path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Configura logger básico
import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("sync_vectors")

from app.agents.knowledge import get_product_knowledge, get_product_documents

def sync_vectors():
    logger.info("🔄 Iniciando sincronização SQL -> ChromaDb...")
    
    # 1. Obter Knowledge (Singleton)
    try:
        kb = get_product_knowledge()
        logger.info("✅ Knowledge/ChromaDb inicializado.")
    except Exception as e:
        logger.error(f"❌ Falha ao inicializar Knowledge: {e}")
        return

    # 2. Ler documentos do SQL
    try:
        docs = get_product_documents()
        logger.info(f"📦 {len(docs)} documentos recuperados do SQL.")
    except Exception as e:
        logger.error(f"❌ Falha ao ler documentos do SQL: {e}")
        return

    # 3. Upsert no Chroma
    if docs:
        try:
            logger.info("🚀 Enviando para ChromaDb (Upsert)...")
            kb.vector_db.upsert(content_hash="seed_v1", documents=docs)
            logger.info("🎉 Sucesso! Documentos indexados.")
        except Exception as e:
            logger.error(f"❌ Erro durante upsert no ChromaDb: {e}")
    else:
        logger.warning("⚠️ Nenhum documento para indexar.")

if __name__ == "__main__":
    sync_vectors()
