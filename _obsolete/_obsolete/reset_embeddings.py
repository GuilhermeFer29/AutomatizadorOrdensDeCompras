#!/usr/bin/env python3
"""
Script para resetar embeddings do ChromaDB.

USE APENAS quando mudar de modelo de embeddings.
Deleta todas as collections antigas e recria com novo modelo.

Motivo: Mudança de dimensões (384 → 768)
- Antes: sentence-transformers (all-MiniLM-L6-v2) = 384 dim
- Agora: Gemini (text-embedding-004) = 768 dim
"""

import sys
from pathlib import Path

# Adiciona app ao path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.rag_service import reset_collections, index_product_catalog
from app.core.database import get_session

def main():
    print("=" * 60)
    print("🔄 RESETANDO EMBEDDINGS DO CHROMADB")
    print("=" * 60)
    print()
    print("⚠️  ATENÇÃO: Este script irá deletar TODOS os embeddings existentes!")
    print("    - Collections antigas (384 dim) serão removidas")
    print("    - Novas collections (768 dim) serão criadas")
    print()
    
    resposta = input("Deseja continuar? (sim/não): ").strip().lower()
    
    if resposta not in ['sim', 's', 'yes', 'y']:
        print("❌ Operação cancelada")
        return
    
    print()
    print("1️⃣  Deletando collections antigas...")
    reset_collections()
    
    print()
    print("2️⃣  Reindexando catálogo de produtos com Gemini embeddings...")
    with get_session() as session:
        index_product_catalog(session)
    
    print()
    print("✅ CONCLUÍDO!")
    print()
    print("Próximos passos:")
    print("  1. Embeddings de chat serão criados automaticamente")
    print("  2. Teste a busca semântica no chat")
    print("  3. Dimensões agora: 768 (Gemini text-embedding-004)")

if __name__ == "__main__":
    main()
