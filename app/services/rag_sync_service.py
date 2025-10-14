"""
Serviço de Sincronização Automática do RAG com Banco de Dados.

Este serviço garante que o ChromaDB esteja sempre sincronizado com o banco MySQL,
reindexando automaticamente quando houver mudanças nos produtos.

FUNCIONAMENTO:
==============
1. Na inicialização: Indexa todos os produtos do banco
2. Em atualizações: Re-indexa substituindo dados antigos (sem acumular)
3. Sempre limpa antes de reindexar para manter dados frescos

MODELOS UTILIZADOS:
===================
• Embeddings: Google text-embedding-004 (768 dimensões)
• LLM RAG: Gemini 2.5 Flash

Autor: Sistema de Automação de Compras
Data: 2025-10-14
"""

from __future__ import annotations
import logging
from datetime import datetime
from pathlib import Path
import shutil
from typing import Optional

from sqlmodel import Session, select
from app.models.models import Produto
from app.core.database import engine

logger = logging.getLogger(__name__)

# Diretório do ChromaDB
CHROMA_DIR = Path(__file__).resolve().parents[2] / "data" / "chroma"


class RAGSyncService:
    """
    Serviço de sincronização automática entre MySQL e ChromaDB.
    
    Responsável por manter o vector store sempre atualizado com os produtos
    do banco de dados, sem acúmulo de dados antigos.
    """
    
    def __init__(self):
        """Inicializa o serviço de sincronização."""
        self.last_sync: Optional[datetime] = None
        self.total_products_indexed: int = 0
        self.is_initialized: bool = False
    
    def clear_vector_store(self) -> None:
        """
        Limpa completamente o ChromaDB para evitar acúmulo de dados.
        
        IMPORTANTE: Sempre executado antes de reindexar para garantir
        que apenas dados atuais estejam no vector store.
        """
        try:
            if CHROMA_DIR.exists():
                logger.info(f"🗑️ Limpando ChromaDB antigo: {CHROMA_DIR}")
                shutil.rmtree(CHROMA_DIR)
                logger.info("✅ ChromaDB limpo com sucesso")
            else:
                logger.info("📂 ChromaDB não existe ainda, será criado na indexação")
        except Exception as e:
            logger.error(f"❌ Erro ao limpar ChromaDB: {e}")
            raise
    
    def sync_full_catalog(self, force_clear: bool = True) -> dict:
        """
        Sincroniza o catálogo completo de produtos do banco para o ChromaDB.
        
        Args:
            force_clear: Se True, limpa ChromaDB antes de indexar (padrão: True)
                        Isso evita acúmulo de dados antigos.
        
        Returns:
            dict: Estatísticas da sincronização
            
        Raises:
            Exception: Se houver erro na indexação
        """
        start_time = datetime.now()
        
        try:
            # 1. Limpar vector store antigo (sem acúmulo)
            if force_clear:
                self.clear_vector_store()
            
            # 2. Carregar produtos do banco
            with Session(engine) as session:
                products = session.exec(select(Produto)).all()
                product_count = len(products)
                
                if product_count == 0:
                    logger.warning("⚠️ Nenhum produto encontrado no banco de dados")
                    return {
                        "status": "warning",
                        "message": "Nenhum produto para indexar",
                        "products_indexed": 0,
                        "duration_seconds": 0
                    }
                
                logger.info(f"📦 Encontrados {product_count} produtos no banco")
                
                # 3. Indexar produtos no ChromaDB
                from app.services.rag_service import index_product_catalog
                
                logger.info("🚀 Iniciando indexação no ChromaDB...")
                index_product_catalog(session)
                
                # 4. Atualizar estatísticas
                self.last_sync = datetime.now()
                self.total_products_indexed = product_count
                self.is_initialized = True
                
                duration = (datetime.now() - start_time).total_seconds()
                
                logger.info(f"✅ Sincronização concluída: {product_count} produtos em {duration:.2f}s")
                
                return {
                    "status": "success",
                    "message": f"ChromaDB sincronizado com sucesso",
                    "products_indexed": product_count,
                    "duration_seconds": round(duration, 2),
                    "synced_at": self.last_sync.isoformat(),
                    "chroma_dir": str(CHROMA_DIR)
                }
                
        except Exception as e:
            logger.error(f"❌ Erro na sincronização do RAG: {e}")
            import traceback
            traceback.print_exc()
            
            return {
                "status": "error",
                "message": f"Erro na sincronização: {str(e)}",
                "products_indexed": 0,
                "duration_seconds": 0
            }
    
    def sync_product_update(self, product_id: int) -> dict:
        """
        Sincroniza atualização de um produto específico.
        
        NOTA: Por enquanto, re-indexa todo o catálogo para garantir consistência.
        Em versões futuras, pode ser otimizado para atualização incremental.
        
        Args:
            product_id: ID do produto atualizado
            
        Returns:
            dict: Resultado da sincronização
        """
        logger.info(f"🔄 Produto {product_id} atualizado, re-sincronizando catálogo...")
        return self.sync_full_catalog(force_clear=True)
    
    def sync_product_delete(self, product_id: int) -> dict:
        """
        Sincroniza exclusão de um produto.
        
        Remove o produto do ChromaDB re-indexando todo o catálogo.
        
        Args:
            product_id: ID do produto deletado
            
        Returns:
            dict: Resultado da sincronização
        """
        logger.info(f"🗑️ Produto {product_id} deletado, re-sincronizando catálogo...")
        return self.sync_full_catalog(force_clear=True)
    
    def get_sync_status(self) -> dict:
        """
        Retorna o status atual da sincronização.
        
        Returns:
            dict: Informações sobre o estado da sincronização
        """
        return {
            "is_initialized": self.is_initialized,
            "last_sync": self.last_sync.isoformat() if self.last_sync else None,
            "total_products_indexed": self.total_products_indexed,
            "chroma_dir_exists": CHROMA_DIR.exists(),
            "chroma_dir_path": str(CHROMA_DIR)
        }


# Instância global do serviço (singleton)
rag_sync_service = RAGSyncService()


def initialize_rag_on_startup() -> dict:
    """
    Função helper para inicialização do RAG no startup da aplicação.
    
    Esta função deve ser chamada no evento @app.on_event("startup") do FastAPI.
    
    Returns:
        dict: Resultado da inicialização
    """
    logger.info("=" * 80)
    logger.info("🚀 INICIALIZANDO RAG AUTOMÁTICO")
    logger.info("=" * 80)
    
    result = rag_sync_service.sync_full_catalog(force_clear=True)
    
    if result["status"] == "success":
        logger.info("=" * 80)
        logger.info("✅ RAG INICIALIZADO COM SUCESSO")
        logger.info(f"   • Produtos indexados: {result['products_indexed']}")
        logger.info(f"   • Tempo: {result['duration_seconds']}s")
        logger.info(f"   • ChromaDB: {result['chroma_dir']}")
        logger.info("=" * 80)
    else:
        logger.error("=" * 80)
        logger.error("❌ FALHA NA INICIALIZAÇÃO DO RAG")
        logger.error(f"   • Erro: {result['message']}")
        logger.error("=" * 80)
    
    return result


def trigger_rag_sync() -> dict:
    """
    Trigger manual para sincronização do RAG.
    
    Pode ser chamado via endpoint API ou manualmente quando necessário.
    
    Returns:
        dict: Resultado da sincronização
    """
    logger.info("🔄 Sincronização manual do RAG acionada")
    return rag_sync_service.sync_full_catalog(force_clear=True)
