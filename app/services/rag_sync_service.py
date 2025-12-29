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
# Diretório do ChromaDB (Volume persistente dedicado do Docker)
CHROMA_DIR = Path("/data/chroma")


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
        Limpa a collection do ChromaDB usando a API nativa.
        
        IMPORTANTE: Usamos delete_collection ao invés de deletar arquivos
        para evitar conflitos com handles SQLite abertos pelo processo.
        """
        try:
            from app.agents.knowledge import get_product_knowledge, reset_knowledge_singleton
            
            logger.info("🗑️ Limpando collection do ChromaDB via API...")
            
            # Get the current knowledge instance to access its client
            kb = get_product_knowledge()
            client = kb.vector_db.client
            
            # Delete collections using ChromaDB's native API
            try:
                client.delete_collection("products_agno")
                logger.info("✅ Collection 'products_agno' deletada")
            except Exception as e:
                logger.info(f"ℹ️ Collection 'products_agno' não existe: {e}")
            
            # Reset the singleton so a fresh client/collection is created
            reset_knowledge_singleton()
            
            logger.info("✅ ChromaDB limpo com sucesso via API")
            
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
    Inclui retry para aguardar o banco de dados estar pronto.
    
    Returns:
        dict: Resultado da inicialização
    """
    import time
    
    logger.info("=" * 80)
    logger.info("🚀 INICIALIZANDO RAG AUTOMÁTICO")
    logger.info("=" * 80)
    
    # Retry logic: aguarda banco de dados estar pronto
    max_retries = 5
    retry_delay = 2  # segundos
    
    for attempt in range(1, max_retries + 1):
        logger.info(f"🔄 Tentativa {attempt}/{max_retries} de sincronização...")
        
        result = rag_sync_service.sync_full_catalog(force_clear=True)
        
        if result["status"] == "success" and result["products_indexed"] > 0:
            logger.info("=" * 80)
            logger.info("✅ RAG INICIALIZADO COM SUCESSO")
            logger.info(f"   • Produtos indexados: {result['products_indexed']}")
            logger.info(f"   • Tempo: {result['duration_seconds']}s")
            logger.info(f"   • ChromaDB: {result['chroma_dir']}")
            logger.info("=" * 80)
            return result
        
        if attempt < max_retries:
            logger.warning(f"⏳ Nenhum produto encontrado, aguardando {retry_delay}s antes de tentar novamente...")
            time.sleep(retry_delay)
    
    # Se chegou aqui, todas as tentativas falharam
    logger.warning("=" * 80)
    logger.warning("⚠️ RAG NÃO INICIALIZADO (Esperado se não há produtos)")
    logger.warning(f"   • Motivo: {result['message']}")
    logger.warning(f"   • Tentativas: {max_retries}")
    logger.warning("   • A API continuará funcionando normalmente")
    logger.warning("=" * 80)
    
    # Retornar warning em vez de erro para não bloquear a API
    return {
        "status": "warning",
        "message": result['message'],
        "products_indexed": 0,
        "duration_seconds": 0
    }


def trigger_rag_sync() -> dict:
    """
    Trigger manual para sincronização do RAG.
    
    Pode ser chamado via endpoint API ou manualmente quando necessário.
    
    Returns:
        dict: Resultado da sincronização
    """
    logger.info("🔄 Sincronização manual do RAG acionada")
    return rag_sync_service.sync_full_catalog(force_clear=True)
