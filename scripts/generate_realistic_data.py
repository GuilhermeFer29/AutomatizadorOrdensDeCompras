"""
Geração de dados sintéticos de alta fidelidade para treinamento de modelos de ML.

Este script gera histórico realista de preços e vendas com:
- Tendências temporais
- Sazonalidade (anual, semanal, datas comemorativas)
- Correlação entre preço e demanda
- Ruído natural do mercado
- Padrões de fins de semana e feriados

ARQUITETURA:
============
✅ 365 dias de histórico mínimo por produto
✅ Modelagem de sazonalidade com funções trigonométricas
✅ Correlação negativa preço-demanda
✅ Picos em datas comemorativas brasileiras
✅ Dados marcados como sintéticos (is_synthetic=True)
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import List, Tuple

import numpy as np
from sqlmodel import Session, select

# Setup path para imports
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.core.database import engine
from app.models.models import PrecosHistoricos, Produto, VendasHistoricas

# Configurações
DAYS_OF_HISTORY = 365
RANDOM_SEED = 42

# Datas comemorativas brasileiras (aproximadas para qualquer ano)
COMMEMORATIVE_DATES = [
    (1, 1),   # Ano Novo
    (2, 14),  # Dia dos Namorados
    (3, 8),   # Dia das Mulheres
    (5, 12),  # Dia das Mães (aproximado, 2º domingo de maio)
    (6, 12),  # Dia dos Namorados
    (8, 11),  # Dia dos Pais (aproximado, 2º domingo de agosto)
    (10, 12), # Dia das Crianças
    (11, 2),  # Finados
    (11, 15), # Proclamação da República
    (11, 25), # Black Friday (aproximado)
    (12, 25), # Natal
]


def _is_weekend(date: datetime) -> bool:
    """Verifica se a data é fim de semana."""
    return date.weekday() >= 5  # Sábado = 5, Domingo = 6


def _is_commemorative(date: datetime, tolerance_days: int = 7) -> bool:
    """Verifica se a data está próxima de uma data comemorativa."""
    # Remover timezone para comparação (se houver)
    date_naive = date.replace(tzinfo=None) if date.tzinfo else date
    
    for month, day in COMMEMORATIVE_DATES:
        comm_date = datetime(date_naive.year, month, day)
        delta = abs((date_naive - comm_date).days)
        if delta <= tolerance_days:
            return True
    return False


def _generate_price_series(
    produto: Produto,
    start_date: datetime,
    days: int,
    seed: int,
) -> List[Tuple[datetime, float]]:
    """
    Gera série temporal de preços com tendência, sazonalidade e ruído.
    
    Componentes:
    - Preço base: Derivado do ID do produto
    - Tendência: Crescimento linear leve
    - Sazonalidade anual: Ciclo senoidal
    - Sazonalidade semanal: Pequenos picos em fins de semana
    - Picos em datas comemorativas: Aumento de 5-15%
    - Ruído: Variação diária aleatória de ±3%
    """
    np.random.seed(seed + produto.id)
    
    # Preço base (variando entre R$ 50 e R$ 500 baseado no ID)
    base_price = 50.0 + (produto.id % 10) * 45.0
    
    prices = []
    
    # Iniciar com preço base (preço do dia 0)
    current_price = base_price
    
    for day in range(days):
        current_date = start_date + timedelta(days=day)
        t = day / days  # Tempo normalizado [0, 1]
        
        # 1. Tendência SUAVE: +0.02% por dia (+7.3% ao ano)
        trend_factor = 1.0002  # Crescimento diário de 0.02%
        
        # 2. Sazonalidade anual (MUITO SUTIL)
        annual_cycle = 0.015 * np.sin(2 * np.pi * t)  # ±1.5% ao longo do ano
        
        # 3. Variação de fim de semana (MÍNIMA)
        weekend_variation = 0.0
        if _is_weekend(current_date):
            weekend_variation = np.random.uniform(-0.005, 0.01)  # -0.5% a +1%
        
        # 4. Datas comemorativas (MODERADO)
        commemorative_boost = 0.0
        if _is_commemorative(current_date, tolerance_days=3):
            commemorative_boost = np.random.uniform(0.02, 0.05)  # +2% a +5%
        
        # 5. Ruído diário REALISTA (PEQUENO)
        # Random walk: movimento browniano com drift
        daily_change = np.random.normal(0, 0.015)  # ±1.5% desvio padrão
        
        # APLICAR MUDANÇAS DE FORMA INCREMENTAL (Random Walk)
        # Novo preço = preço anterior × (1 + mudanças pequenas)
        price_multiplier = (
            trend_factor *  # Tendência suave
            (1 + annual_cycle) *  # Ciclo anual
            (1 + weekend_variation) *  # Fim de semana
            (1 + commemorative_boost) *  # Datas especiais
            (1 + daily_change)  # Random walk
        )
        
        current_price = current_price * price_multiplier
        
        # Limites de sanidade (não permite variações absurdas)
        current_price = np.clip(current_price, base_price * 0.7, base_price * 1.5)
        
        prices.append((current_date, round(float(current_price), 2)))
    
    return prices


def _generate_sales_series(
    produto: Produto,
    price_series: List[Tuple[datetime, float]],
    seed: int,
) -> List[Tuple[datetime, int, float]]:
    """
    Gera série temporal de vendas correlacionada com preços.
    
    Componentes:
    - Demanda base: Derivada do estoque mínimo
    - Correlação negativa com preço: Vendas caem quando preço sobe
    - Padrão semanal: Mais vendas nos fins de semana
    - Picos em datas comemorativas: Aumento de 30-80%
    - Ruído: Variação diária aleatória
    """
    np.random.seed(seed + produto.id + 1000)
    
    # Demanda base diária (baseada no estoque mínimo)
    base_demand = max(produto.estoque_minimo / 30, 5)  # Mínimo 5 unidades/dia
    
    # Calcular preço médio da série
    avg_price = np.mean([price for _, price in price_series])
    
    sales = []
    
    for date, price in price_series:
        # 1. Correlação negativa com preço (elasticidade-preço da demanda)
        price_ratio = price / avg_price
        price_effect = 1 / (price_ratio ** 0.5)  # Elasticidade de -0.5
        
        # 2. Padrão semanal (mais vendas nos fins de semana)
        weekend_boost = 1.4 if _is_weekend(date) else 1.0
        
        # 3. Picos em datas comemorativas
        commemorative_boost = 1.0
        if _is_commemorative(date):
            commemorative_boost = np.random.uniform(1.3, 1.8)  # +30% a +80%
        
        # 4. Ruído diário
        daily_noise = np.random.uniform(0.7, 1.3)
        
        # Quantidade de vendas
        quantity = base_demand * price_effect * weekend_boost * commemorative_boost * daily_noise
        quantity = max(int(round(quantity)), 0)  # Garantir não-negativo
        
        # Receita
        revenue = float(quantity * price)
        
        sales.append((date, quantity, revenue))
    
    return sales


def generate_realistic_data(days: int = DAYS_OF_HISTORY, seed: int = RANDOM_SEED) -> dict:
    """
    Gera dados sintéticos realistas para todos os produtos no banco.
    
    Args:
        days: Número de dias de histórico a gerar
        seed: Seed para reprodutibilidade
    
    Returns:
        Dicionário com estatísticas da geração
    """
    print(f"🚀 Iniciando geração de dados sintéticos ({days} dias)...")
    
    with Session(engine) as session:
        # Buscar todos os produtos
        produtos = list(session.exec(select(Produto)).all())
        
        if not produtos:
            print("❌ Nenhum produto encontrado no banco de dados.")
            print("   Execute 'python scripts/seed_database.py' primeiro.")
            return {"error": "no_products"}
        
        print(f"📦 Encontrados {len(produtos)} produtos para gerar histórico.")
        
        # Data de início (365 dias atrás)
        end_date = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        start_date = end_date - timedelta(days=days - 1)
        
        total_prices = 0
        total_sales = 0
        
        for idx, produto in enumerate(produtos, 1):
            print(f"  [{idx}/{len(produtos)}] Gerando dados para {produto.sku} ({produto.nome})...")
            
            # Gerar série de preços
            price_series = _generate_price_series(produto, start_date, days, seed)
            
            # Gerar série de vendas correlacionada
            sales_series = _generate_sales_series(produto, price_series, seed)
            
            # Inserir preços no banco
            for date, price in price_series:
                preco_historico = PrecosHistoricos(
                    produto_id=produto.id,
                    fornecedor="Fornecedor Sintético",
                    preco=Decimal(str(price)),
                    moeda="BRL",
                    coletado_em=date,
                    is_synthetic=True,
                )
                session.add(preco_historico)
                total_prices += 1
            
            # Inserir vendas no banco
            for date, quantity, revenue in sales_series:
                venda_historica = VendasHistoricas(
                    produto_id=produto.id,
                    data_venda=date,
                    quantidade=quantity,
                    receita=Decimal(str(round(revenue, 2))),
                    criado_em=datetime.now(timezone.utc),
                )
                session.add(venda_historica)
                total_sales += 1
        
        # Commit em lote
        print("\n💾 Salvando dados no banco...")
        session.commit()
        
        print("\n✅ Geração concluída com sucesso!")
        print(f"📊 Estatísticas:")
        print(f"   - Produtos processados: {len(produtos)}")
        print(f"   - Registros de preços: {total_prices:,}")
        print(f"   - Registros de vendas: {total_sales:,}")
        print(f"   - Período: {start_date.date()} a {end_date.date()}")
        
        return {
            "success": True,
            "produtos": len(produtos),
            "precos": total_prices,
            "vendas": total_sales,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
        }


def clear_synthetic_data() -> dict:
    """Remove todos os dados sintéticos do banco."""
    print("🗑️  Removendo dados sintéticos existentes...")
    
    with Session(engine) as session:
        # Remover preços sintéticos
        precos_result = session.exec(
            select(PrecosHistoricos).where(PrecosHistoricos.is_synthetic == True)
        )
        precos_count = sum(1 for _ in precos_result)
        
        session.exec(
            "DELETE FROM precos_historicos WHERE is_synthetic = TRUE"
        )
        
        # Remover todas as vendas (assumindo que são sintéticas se os preços são)
        session.exec("DELETE FROM vendas_historicas")
        
        session.commit()
        
        print(f"✅ Removidos {precos_count:,} registros de preços sintéticos")
        print(f"✅ Removidos todos os registros de vendas")
        
        return {"precos_removed": precos_count}


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Gera dados sintéticos realistas para ML")
    parser.add_argument(
        "--days",
        type=int,
        default=DAYS_OF_HISTORY,
        help=f"Número de dias de histórico (padrão: {DAYS_OF_HISTORY})",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=RANDOM_SEED,
        help=f"Seed para reprodutibilidade (padrão: {RANDOM_SEED})",
    )
    parser.add_argument(
        "--clear",
        action="store_true",
        help="Remove dados sintéticos existentes antes de gerar novos",
    )
    
    args = parser.parse_args()
    
    if args.clear:
        clear_synthetic_data()
        print()
    
    result = generate_realistic_data(days=args.days, seed=args.seed)
    
    if result.get("error"):
        sys.exit(1)
