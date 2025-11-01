"""
Script para adicionar features de mercado às tabelas existentes.
Adiciona colunas confiabilidade e prazo_entrega_dias ao Fornecedor.
Cria tabela OfertaProduto se não existir.
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy import text
from app.core.database import engine


def migrate_supplier_features():
    """Adiciona novas colunas e tabelas para features de mercado."""
    
    print("=" * 70)
    print("🔧 MIGRAÇÃO: Features de Mercado para Fornecedores")
    print("=" * 70)
    print()
    
    with engine.begin() as conn:
        # 1. Adicionar coluna confiabilidade se não existir
        print("1️⃣ Adicionando coluna 'confiabilidade' em fornecedores...")
        try:
            conn.execute(text("""
                ALTER TABLE fornecedores 
                ADD COLUMN confiabilidade FLOAT DEFAULT 0.9
            """))
            print("   ✅ Coluna 'confiabilidade' adicionada")
        except Exception as e:
            if "Duplicate column" in str(e) or "already exists" in str(e):
                print("   ⚠️  Coluna 'confiabilidade' já existe")
            else:
                print(f"   ❌ Erro: {e}")
        
        # 2. Adicionar coluna prazo_entrega_dias se não existir
        print("2️⃣ Adicionando coluna 'prazo_entrega_dias' em fornecedores...")
        try:
            conn.execute(text("""
                ALTER TABLE fornecedores 
                ADD COLUMN prazo_entrega_dias INT DEFAULT 7
            """))
            print("   ✅ Coluna 'prazo_entrega_dias' adicionada")
        except Exception as e:
            if "Duplicate column" in str(e) or "already exists" in str(e):
                print("   ⚠️  Coluna 'prazo_entrega_dias' já existe")
            else:
                print(f"   ❌ Erro: {e}")
        
        # 3. Criar tabela ofertas_produtos se não existir
        print("3️⃣ Criando tabela 'ofertas_produtos'...")
        try:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS ofertas_produtos (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    produto_id INT NOT NULL,
                    fornecedor_id INT NOT NULL,
                    preco_ofertado DECIMAL(10, 2) NOT NULL,
                    estoque_disponivel INT DEFAULT 100,
                    validade_oferta DATETIME NULL,
                    criado_em DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    atualizado_em DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    
                    FOREIGN KEY (produto_id) REFERENCES produtos(id) ON DELETE CASCADE,
                    FOREIGN KEY (fornecedor_id) REFERENCES fornecedores(id) ON DELETE CASCADE,
                    
                    INDEX idx_ofertas_produto (produto_id),
                    INDEX idx_ofertas_fornecedor (fornecedor_id),
                    INDEX idx_ofertas_preco (preco_ofertado),
                    INDEX idx_ofertas_produto_preco (produto_id, preco_ofertado)
                )
            """))
            print("   ✅ Tabela 'ofertas_produtos' criada")
        except Exception as e:
            if "already exists" in str(e):
                print("   ⚠️  Tabela 'ofertas_produtos' já existe")
            else:
                print(f"   ❌ Erro: {e}")
    
    print()
    print("=" * 70)
    print("✅ MIGRAÇÃO CONCLUÍDA COM SUCESSO!")
    print("=" * 70)
    print()
    print("🎯 Próximo passo: Gerar fornecedores e ofertas")
    print("   docker compose exec api python scripts/setup_development.py generate_suppliers")
    print()


if __name__ == "__main__":
    try:
        migrate_supplier_features()
    except Exception as e:
        print(f"\n❌ Erro na migração: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
