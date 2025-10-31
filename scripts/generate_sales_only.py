#!/usr/bin/env python3
"""
Gera apenas histórico de vendas (sem tentar limpar preços).
Usado após seed_price_history.py para evitar deadlocks.
"""

import sys
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import numpy as np
import pandas as pd
from sqlmodel import Session, select

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.core.database import engine
from app.models.models import Produto, VendasHistoricas, PrecosHistoricos

DAYS_OF_HISTORY = 365
RANDOM_SEED = 42


def _is_weekend(date: datetime) -> bool:
    """Verifica se a data é fim de semana."""
    return date.weekday() >= 5


def _is_commemorative(date: datetime, tolerance_days: int = 7) -> bool:
    """Verifica se a data está próxima de uma data comemorativa."""
    COMMEMORATIVE_DATES = [
        (1, 1), (2, 14), (3, 8), (5, 12), (6, 12), (8, 11),
        (10, 12), (11, 2), (11, 15), (11, 25), (12, 25),
    ]
    
    date_naive = date.replace(tzinfo=None) if date.tzinfo else date
    
    for month, day in COMMEMORATIVE_DATES:
        comm_date = datetime(date_naive.year, month, day)
        delta = abs((date_naive - comm_date).days)
        if delta <= tolerance_days:
            return True
    return False


def generate_sales_for_product(
    produto: Produto,
    start_date: datetime,
    days: int,
    seed: int,
) -> list:
    """Gera série temporal de vendas correlacionada com preços."""
    np.random.seed(seed + produto.id + 1000)
    
    # Demanda base
    base_demand = max(produto.estoque_minimo / 30, 5)
    
    sales = []
    
    for day in range(days):
        current_date = start_date + timedelta(days=day)
        
        # Padrão semanal
        weekend_boost = 1.4 if _is_weekend(current_date) else 1.0
        
        # Picos em datas comemorativas
        commemorative_boost = 1.0
        if _is_commemorative(current_date):
            commemorative_boost = np.random.uniform(1.3, 1.8)
        
        # Ruído diário
        daily_noise = np.random.uniform(0.7, 1.3)
        
        # Quantidade
        quantity = base_demand * weekend_boost * commemorative_boost * daily_noise
        quantity = max(int(round(quantity)), 0)
        
        # Buscar preço do dia (ou usar preço médio)
        revenue = float(quantity * (50 + (produto.id % 10) * 45))
        
        sales.append((current_date, quantity, revenue))
    
    return sales


def main():
    """Gera vendas para todos os produtos."""
    print("🚀 Gerando histórico de vendas (365 dias)...")
    
    with Session(engine) as session:
        produtos = list(session.exec(select(Produto)).all())
        
        if not produtos:
            print("❌ Nenhum produto encontrado")
            return False
        
        print(f"📦 Gerando vendas para {len(produtos)} produtos...")
        
        end_date = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        start_date = end_date - timedelta(days=DAYS_OF_HISTORY - 1)
        
        total_sales = 0
        
        for idx, produto in enumerate(produtos, 1):
            if idx % 100 == 0:
                print(f"  [{idx}/{len(produtos)}] Gerando vendas...")
            
            sales_series = generate_sales_for_product(produto, start_date, DAYS_OF_HISTORY, RANDOM_SEED)
            
            for date, quantity, revenue in sales_series:
                venda = VendasHistoricas(
                    produto_id=produto.id,
                    data_venda=date,
                    quantidade=quantity,
                    receita=Decimal(str(round(revenue, 2))),
                    criado_em=datetime.now(timezone.utc),
                )
                session.add(venda)
                total_sales += 1
        
        print("💾 Salvando vendas no banco...")
        session.commit()
        
        print(f"\n✅ Geração concluída!")
        print(f"   - Produtos: {len(produtos)}")
        print(f"   - Registros de vendas: {total_sales:,}")
        print(f"   - Período: {start_date.date()} a {end_date.date()}")
        
        return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
