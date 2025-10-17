"""
Script para criar todas as tabelas do banco de dados usando SQLModel.
Inclui as novas tabelas de fornecedores e ofertas.
"""

import sys
from pathlib import Path

# Adicionar o diretório raiz ao path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from sqlmodel import SQLModel
from app.core.database import engine
from app.models.models import (
    Produto,
    PrecosHistoricos,
    VendasHistoricas,
    Fornecedor,
    OfertaProduto,
    OrdemDeCompra,
    Agente,
    ChatSession,
    ChatMessage,
    ChatContext,
    ChatAction,
)


def create_all_tables():
    """Cria todas as tabelas definidas nos modelos SQLModel."""
    print("=" * 70)
    print("🔧 CRIAÇÃO DE TABELAS DO BANCO DE DADOS")
    print("=" * 70)
    print()
    
    print("📊 Modelos registrados:")
    print("  • Produto")
    print("  • PrecosHistoricos")
    print("  • VendasHistoricas")
    print("  • Fornecedor (com confiabilidade e prazo)")
    print("  • OfertaProduto (mercado sintético)")
    print("  • OrdemDeCompra")
    print("  • Agente")
    print("  • ChatSession, ChatMessage, ChatContext, ChatAction")
    print()
    
    try:
        print("⚙️  Criando tabelas...")
        SQLModel.metadata.create_all(engine)
        
        print("✅ Todas as tabelas criadas com sucesso!")
        print()
        print("=" * 70)
        print("🎯 PRÓXIMOS PASSOS:")
        print("=" * 70)
        print()
        print("1. Gerar fornecedores e ofertas:")
        print("   docker compose exec api python scripts/setup_development.py generate_suppliers")
        print()
        print("2. Ou gerar dados completos para ML:")
        print("   docker compose exec api python scripts/setup_development.py generate_data")
        print()
        
    except Exception as e:
        print(f"❌ Erro ao criar tabelas: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    create_all_tables()
