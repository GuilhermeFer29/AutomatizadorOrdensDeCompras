"""
Singleton para gerenciamento centralizado do ChromaDB.

ARQUITETURA DE PRODUÇÃO:
========================
Este módulo é a ÚNICA fonte de verdade para conexões com o ChromaDB.
Tanto o Agno (KnowledgeBase) quanto o LangChain (Chroma) devem usar
o cliente retornado por `get_vector_db_client()`.

PROBLEMAS RESOLVIDOS:
- "An instance of Chroma already exists with different settings"
- Múltiplas conexões concorrentes causando locks
- Memory leaks por instâncias não gerenciadas

REFERÊNCIAS:
- ChromaDB Docs: https://docs.trychroma.com/
- Design Pattern: Singleton (GoF)

Autor: Sistema PMI | Data: 2026-01-14
"""

from __future__ import annotations

import os
import threading
from pathlib import Path
from typing import Optional

import chromadb
from chromadb.config import Settings


class VectorDBManager:
    """
    Singleton thread-safe para gerenciar conexão com ChromaDB.
    
    Garante uma única instância do PersistentClient em toda a aplicação,
    evitando conflitos de configuração e conexões duplicadas.
    """
    
    _instance: Optional[chromadb.PersistentClient] = None
    _lock: threading.Lock = threading.Lock()
    _persist_directory: Optional[str] = None
    _initialized: bool = False
    
    # Diretório padrão: volume Docker persistente
    DEFAULT_PERSIST_DIR = "/data/chroma"
    
    @classmethod
    def get_client(cls) -> chromadb.PersistentClient:
        """
        Retorna o cliente ChromaDB singleton.
        
        Thread-safe: usa double-checked locking para performance.
        
        Returns:
            chromadb.PersistentClient: Instância única compartilhada
            
        Raises:
            RuntimeError: Se não conseguir inicializar o ChromaDB
        """
        # Fast path: já inicializado
        if cls._instance is not None:
            return cls._instance
        
        # Slow path: precisa inicializar (thread-safe)
        with cls._lock:
            # Double-check após adquirir lock
            if cls._instance is not None:
                return cls._instance
            
            # Determina diretório de persistência
            persist_dir = os.getenv("CHROMA_PERSIST_DIR", cls.DEFAULT_PERSIST_DIR)
            
            # Garante que diretório existe
            Path(persist_dir).mkdir(parents=True, exist_ok=True)
            
            # Cria cliente com configurações de produção
            try:
                cls._instance = chromadb.PersistentClient(
                    path=persist_dir,
                    settings=Settings(
                        anonymized_telemetry=False,  # Desabilita telemetria
                        allow_reset=False,            # Produção: não permite reset acidental
                        is_persistent=True
                    )
                )
                cls._persist_directory = persist_dir
                cls._initialized = True
                
                print(f"✅ [VectorDB] ChromaDB inicializado: {persist_dir}")
                
            except Exception as e:
                raise RuntimeError(
                    f"❌ Falha ao inicializar ChromaDB em '{persist_dir}': {e}"
                ) from e
            
            return cls._instance
    
    @classmethod
    def get_collection(cls, name: str = "products") -> chromadb.Collection:
        """
        Retorna uma collection específica do ChromaDB.
        
        Args:
            name: Nome da collection (default: "products")
            
        Returns:
            chromadb.Collection: Collection para operações CRUD
        """
        client = cls.get_client()
        return client.get_or_create_collection(
            name=name,
            metadata={"hnsw:space": "cosine"}  # Distância coseno para embeddings
        )
    
    @classmethod
    def get_persist_directory(cls) -> Optional[str]:
        """Retorna o diretório de persistência atual."""
        return cls._persist_directory
    
    @classmethod
    def is_initialized(cls) -> bool:
        """Verifica se o singleton foi inicializado."""
        return cls._initialized
    
    @classmethod
    def reset_for_testing(cls) -> None:
        """
        Reseta o singleton (APENAS PARA TESTES).
        
        ⚠️ NUNCA use em produção! Pode causar inconsistências.
        """
        with cls._lock:
            if cls._instance is not None:
                print(f"🔄 [VectorDB] Resetando cliente (TESTE ONLY)")
            cls._instance = None
            cls._persist_directory = None
            cls._initialized = False


# ============================================================================
# FUNÇÕES HELPER (compatibilidade com código existente)
# ============================================================================

def get_vector_db_client() -> chromadb.PersistentClient:
    """
    Função helper para obter o cliente ChromaDB singleton.
    
    Uso:
        from app.core.vector_db import get_vector_db_client
        client = get_vector_db_client()
    """
    return VectorDBManager.get_client()


def get_products_collection() -> chromadb.Collection:
    """
    Retorna a collection de produtos (atalho comum).
    """
    return VectorDBManager.get_collection("products")


# ============================================================================
# VALIDAÇÃO NO IMPORT (Fail-Fast)
# ============================================================================

def _validate_environment() -> None:
    """
    Valida variáveis de ambiente críticas no import do módulo.
    
    Princípio: Crash-only software - falhar cedo é melhor que falhar tarde.
    """
    persist_dir = os.getenv("CHROMA_PERSIST_DIR", VectorDBManager.DEFAULT_PERSIST_DIR)
    
    # Verifica se o diretório pai é gravável
    parent = Path(persist_dir).parent
    if parent.exists() and not os.access(str(parent), os.W_OK):
        raise RuntimeError(
            f"❌ Diretório '{parent}' não tem permissão de escrita. "
            f"ChromaDB precisa gravar em '{persist_dir}'"
        )


# Executa validação no import (fail-fast)
_validate_environment()


__all__ = [
    "VectorDBManager",
    "get_vector_db_client", 
    "get_products_collection"
]
