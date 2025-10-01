"""Seed the database with historical sales data from a CSV file."""

from __future__ import annotations

import argparse
import logging
import sys
import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from sqlmodel import Session, select
from app.core.database import engine
from app.models.models import Produto

LOGGER = logging.getLogger(__name__)


def parse_arguments() -> argparse.Namespace:
    """Build and parse command-line arguments."""

    parser = argparse.ArgumentParser(description="Seed the MySQL database with sales history data.")
    parser.add_argument("csv_path", nargs="?", default=None, type=Path, help="Path to the CSV file containing sales records (optional, uses default products if not provided).")
    return parser.parse_args()


def configure_logging() -> None:
    """Configure a basic logging handler for CLI execution."""

    logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s:%(message)s")


def seed_from_csv(csv_path: str) -> None:
    """Popula o banco a partir de um arquivo CSV."""
    import pandas as pd
    
    if not os.path.exists(csv_path):
        LOGGER.error(f"❌ Arquivo CSV não encontrado: {csv_path}")
        return
    
    try:
        df = pd.read_csv(
            csv_path,
            on_bad_lines='skip',
            encoding='utf-8',
            engine='python'
        )
        LOGGER.info(f"📂 CSV carregado: {len(df)} linhas")
        
        if len(df) > 0 and df.iloc[0].get('nome') == 'nome':
            df = df.iloc[1:]
            LOGGER.info("🧹 Linha de cabeçalho duplicada removida")
            
    except Exception as e:
        LOGGER.error(f"❌ Erro ao ler CSV: {e}")
        return
    
    # Validar colunas obrigatórias
    if 'nome' not in df.columns:
        LOGGER.error(f"❌ Coluna 'nome' não encontrada. Colunas disponíveis: {df.columns.tolist()}")
        return
    
    with Session(engine) as session:
        criados = 0
        duplicados = 0
        erros = 0
        
        for idx, row in df.iterrows():
            try:
                nome = str(row.get("nome", "")).strip()
                sku = str(row.get("sku", "")).strip()
                
                # Validar nome e sku não vazios
                if not nome or nome.lower() == 'nan':
                    LOGGER.warning(f"⚠️  Linha {idx+1}: nome vazio, pulando")
                    continue
                
                if not sku or sku.lower() == 'nan':
                    LOGGER.warning(f"⚠️  Linha {idx+1}: SKU vazio para '{nome}', pulando")
                    continue
                
                # Verificar se produto já existe (por SKU ou nome)
                existing = session.exec(
                    select(Produto).where(
                        (Produto.sku == sku) | (Produto.nome == nome)
                    )
                ).first()
                
                if existing:
                    duplicados += 1
                    continue
                
                # Criar novo produto com TODOS os campos do CSV
                produto = Produto(
                    sku=sku,
                    nome=nome,
                    categoria=str(row.get("categoria", "")).strip() if "categoria" in row else None,
                    estoque_atual=int(row.get("estoque_atual", 0)) if "estoque_atual" in row else 0,
                    estoque_minimo=int(row.get("estoque_minimo", 0)) if "estoque_minimo" in row else 0
                )
                session.add(produto)
                criados += 1
                
                # Commit parcial a cada 20 produtos para evitar rollback em massa
                if criados % 20 == 0:
                    session.commit()
                    LOGGER.info(f"✅ {criados} produtos criados...")
                    
            except Exception as e:
                erros += 1
                LOGGER.error(f"❌ Erro linha {idx+1} ({row.get('nome', 'N/A')}): {e}")
                session.rollback()  # Rollback da transação atual
                continue
        
        # Commit final
        try:
            session.commit()
        except Exception as e:
            LOGGER.error(f"❌ Erro no commit final: {e}")
            session.rollback()
        
        LOGGER.info(f"🎉 Seed concluído! Criados: {criados} | Duplicados: {duplicados} | Erros: {erros}")


def seed_produtos_padrao() -> None:
    """Popula o banco com produtos de exemplo sem necessidade de CSV."""
    produtos_exemplo = [
        {"nome": "Parafuso M8 Inox", "descricao": "Parafuso métrico 8mm em aço inoxidável", "unidade": "unidade"},
        {"nome": "Rolamento SKF 6205", "descricao": "Rolamento de esferas SKF série 6205", "unidade": "unidade"},
        {"nome": "Correia Dentada HTD 8M", "descricao": "Correia dentada perfil HTD 8M", "unidade": "metro"},
        {"nome": "Óleo Lubrificante SAE 40", "descricao": "Óleo lubrificante mineral SAE 40", "unidade": "litro"},
        {"nome": "Sensor Indutivo M12", "descricao": "Sensor de proximidade indutivo M12 NPN", "unidade": "unidade"},
    ]
    
    with Session(engine) as session:
        for item in produtos_exemplo:
            existing = session.exec(
                select(Produto).where(Produto.nome == item["nome"])
            ).first()
            
            if not existing:
                produto = Produto(**item)
                session.add(produto)
                LOGGER.info(f"✅ Produto criado: {item['nome']}")
            else:
                LOGGER.info(f"⚠️  Produto já existe: {item['nome']}")
        
        session.commit()
        LOGGER.info("🎉 Seed de produtos padrão concluído!")


def main() -> None:
    """Entry point for the seeding script."""

    configure_logging()
    load_dotenv()

    args = parse_arguments()
    if args.csv_path and not args.csv_path.is_file():
        raise FileNotFoundError(f"Arquivo CSV não encontrado: {args.csv_path}")

    if args.csv_path:
        seed_from_csv(args.csv_path)
    else:
        # Se não fornecer CSV, tenta usar o CSV padrão do projeto
        default_csv = Path(__file__).parent.parent / "data" / "products_seed.csv"
        if default_csv.exists():
            LOGGER.info(f"📂 Usando CSV padrão: {default_csv}")
            seed_from_csv(str(default_csv))
        else:
            LOGGER.info("📦 Usando produtos de exemplo")
            seed_produtos_padrao()


if __name__ == "__main__":
    main()
