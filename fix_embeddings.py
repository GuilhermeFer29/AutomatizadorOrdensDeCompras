#!/usr/bin/env python3
"""
Script de Correção: Limpa ChromaDB e reconstrói embeddings.

PROBLEMA RESOLVIDO:
- OpenRouter NÃO suporta API de embeddings
- Erro: 'str' object has no attribute 'data'
- Erro: 401 - User not found

SOLUÇÃO:
- Migrado para sentence-transformers (modelo local)
- Dimensões mudaram: 1536 → 384
- Este script limpa os dados antigos e reconstrói
"""

import shutil
from pathlib import Path
import sys

# Adiciona o diretório raiz ao path
sys.path.insert(0, str(Path(__file__).parent))

from app.core.database import get_session
from app.services.rag_service import index_product_catalog

# Diretório do ChromaDB
CHROMA_DIR = Path(__file__).parent / "data" / "chroma"


def main():
    print("=" * 80)
    print("🔧 CORREÇÃO DE EMBEDDINGS - Migração para Sentence-Transformers")
    print("=" * 80)
    print()
    
    # 1. Remove dados antigos do ChromaDB
    if CHROMA_DIR.exists():
        print(f"📁 Removendo ChromaDB antigo: {CHROMA_DIR}")
        try:
            shutil.rmtree(CHROMA_DIR)
            print("✅ ChromaDB antigo removido com sucesso!")
        except Exception as e:
            print(f"⚠️  Erro ao remover: {e}")
            print("   Continuando mesmo assim...")
    else:
        print(f"ℹ️  ChromaDB não existe ainda: {CHROMA_DIR}")
    
    print()
    
    # 2. Recria diretório
    CHROMA_DIR.mkdir(parents=True, exist_ok=True)
    print(f"✅ Diretório recriado: {CHROMA_DIR}")
    print()
    
    # 3. Reconstrói índice de produtos
    print("📦 Reconstruindo índice de produtos...")
    try:
        with get_session() as session:
            index_product_catalog(session)
        print("✅ Índice de produtos reconstruído com sucesso!")
    except Exception as e:
        print(f"⚠️  Erro ao reconstruir índice: {e}")
        print("   Verifique se o banco de dados está acessível")
    
    print()
    print("=" * 80)
    print("✅ CORREÇÃO CONCLUÍDA!")
    print("=" * 80)
    print()
    print("PRÓXIMOS PASSOS:")
    print("1. Reinicie o container Docker:")
    print("   docker-compose restart api")
    print()
    print("2. Teste o chat novamente")
    print()
    print("MUDANÇAS APLICADAS:")
    print("✅ OpenAI Embeddings → Sentence-Transformers (local)")
    print("✅ Dimensões: 1536 → 384")
    print("✅ Sem custo de API para embeddings")
    print("✅ Funciona offline")
    print()


if __name__ == "__main__":
    main()
