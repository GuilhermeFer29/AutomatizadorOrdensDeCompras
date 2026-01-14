"""
Singleton para gerenciar instância única do ChromaDB.

Este módulo resolve o erro "An instance of Chroma already exists with different settings"
garantindo que apenas uma instância do cliente ChromaDB seja criada e reutilizada
em toda a aplicação.

PROBLEMA RESOLVIDO:
===================
Antes: Múltiplas instâncias do ChromaDB eram criadas com configurações potencialmente
diferentes, causando conflitos.

Solução: Padrão Singleton que garante uma única instância compartilhada do
PersistentClient do ChromaDB.

REFERÊNCIAS:
- ChromaDB Issue #1302: https://github.com/chroma-core/chroma/issues/1302
- Documentação ChromaDB: https://docs.trychroma.com/

Autor: Sistema de Automação de Compras
Data: 2025-10-16
"""

from __future__ import annotations
import os
from pathlib import Path
from typing import Optional
import chromadb
from chromadb.config import Settings


class ChromaClientSingleton:
    """
    Singleton para gerenciar instância única do ChromaDB PersistentClient.
    
    Garante que apenas uma instância do cliente seja criada, evitando o erro:
    "An instance of Chroma already exists with different settings"
    """
    
    _instance: Optional[chromadb.PersistentClient] = None
    _persist_directory: Optional[str] = None
    
    @classmethod
    def get_client(cls, persist_directory: Optional[str] = None) -> chromadb.PersistentClient:
        """
        Retorna a instância única do ChromaDB PersistentClient.
        
        Args:
            persist_directory: Diretório para persistir os dados do ChromaDB.
                              Se None, usa o diretório padrão do projeto.
        
        Returns:
            chromadb.PersistentClient: Instância única do cliente ChromaDB
            
        Raises:
            ValueError: Se tentar mudar o diretório após a primeira inicialização
        """
        # Define diretório padrão se não fornecido
        if persist_directory is None:
            persist_directory = str(
                Path(__file__).resolve().parents[2] / "data" / "chroma"
            )
        
        # Verifica se está tentando mudar o diretório após inicialização
        if cls._instance is not None and cls._persist_directory != persist_directory:
            raise ValueError(
                f"Tentativa de mudar diretório do ChromaDB após inicialização.\n"
                f"Diretório atual: {cls._persist_directory}\n"
                f"Novo diretório solicitado: {persist_directory}\n"
                f"Reinicie a aplicação para mudar o diretório."
            )
        
        # Cria instância apenas na primeira chamada
        if cls._instance is None:
            cls._persist_directory = persist_directory
            
            # Garante que o diretório existe
            Path(persist_directory).mkdir(parents=True, exist_ok=True)
            
            # Cria cliente com configurações consistentes
            cls._instance = chromadb.PersistentClient(
                path=persist_directory,
                settings=Settings(
                    anonymized_telemetry=False,
                    allow_reset=True
                )
            )
            
            print(f"✅ ChromaDB PersistentClient inicializado: {persist_directory}")
        
        return cls._instance
    
    @classmethod
    def reset_client(cls) -> None:
        """
        Reseta a instância do cliente (útil para testes ou reinicialização).
        
        ATENÇÃO: Use com cuidado! Isso força a criação de uma nova instância.
        """
        if cls._instance is not None:
            print(f"🔄 Resetando ChromaDB client: {cls._persist_directory}")
            cls._instance = None
            cls._persist_directory = None
    
    @classmethod
    def get_persist_directory(cls) -> Optional[str]:
        """
        Retorna o diretório de persistência atual.
        
        Returns:
            str: Caminho do diretório ou None se não inicializado
        """
        return cls._persist_directory


# Função helper para compatibilidade com código existente
def get_chroma_client(persist_directory: Optional[str] = None) -> chromadb.PersistentClient:
    """
    Função helper para obter o cliente ChromaDB singleton.
    
    Args:
        persist_directory: Diretório para persistir os dados (opcional)
    
    Returns:
        chromadb.PersistentClient: Instância única do cliente
    """
    return ChromaClientSingleton.get_client(persist_directory)
