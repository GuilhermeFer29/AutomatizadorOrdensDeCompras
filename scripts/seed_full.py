#!/usr/bin/env python3
"""
=============================================================================
 SEED COMPLETO — Geração de Dados Realistas para Todo o Projeto
=============================================================================

 Script ÚNICO que popula o banco de dados inteiro com dados fiéis de uma
 empresa de estofados / supply-chain industrial.

 O que é gerado (em ordem de dependência):
 ─────────────────────────────────────────
 1. Tenant (empresa)
 2. Usuários (owner + operadores)
 3. Fornecedores reais com localização e métricas
 4. Catálogo de produtos (50 SKUs do CSV ou hardcoded)
 5. Ofertas de fornecedores por produto (mercado simulado)
 6. Histórico de preços — 365 dias com random-walk + sazonalidade BR
 7. Histórico de vendas — 365 dias correlacionados com preço
 8. Ordens de compra recentes (30 dias, mix auto/manual)
 9. Auditoria de decisões dos agentes
10. Agentes IA configurados
11. Sessão de chat + mensagens de exemplo

 EXECUÇÃO:
 ─────────
   # Via Docker (produção):
   docker compose exec api python scripts/seed_full.py

   # Com opções:
   docker compose exec api python scripts/seed_full.py --days 365 --clear

   # Sem apagar dados existentes, apenas complementando:
   docker compose exec api python scripts/seed_full.py --only-missing

 SEGURANÇA:
 ──────────
 - NÃO faz DROP ALL / drop_all — preserva schema e tenants existentes
 - Flag --clear remove apenas dados de negócio (vendas, preços, ordens…)
 - Sem --clear, faz upsert (pula duplicatas)

Autor: Automação PMI | Data: 2026-02-07
"""

from __future__ import annotations

import argparse
import csv
import logging
import os
import random
import sys
import time
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from uuid import UUID, uuid4

import numpy as np
from sqlalchemy import text
from sqlmodel import Session, select

# ── Setup path ──────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy import create_engine as sa_create_engine
from app.models.models import (
    Agente,
    AuditoriaDecisao,
    ChatAction,
    ChatContext,
    ChatMessage,
    ChatSession,
    Fornecedor,
    ModeloPredicao,
    OfertaProduto,
    OrdemDeCompra,
    PrecosHistoricos,
    Produto,
    Tenant,
    User,
    VendasHistoricas,
)

# ── Logging ─────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(message)s",
    datefmt="%H:%M:%S",
)
LOG = logging.getLogger("seed_full")

# Engine dedicado para seed: pool maior e timeout longo
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "mysql+pymysql://app_user:app_password@db:3306/app_db",
)
engine = sa_create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_size=2,
    max_overflow=3,
    pool_timeout=120,
    pool_recycle=300,
)

# ── Configurações ───────────────────────────────────────────────────────────
RANDOM_SEED = 42
DAYS_OF_HISTORY = 365
DEFAULT_PASSWORD = "SeedAdmin1"  # Atende regra: 8+ chars, uppercase, lowercase, digit

# Datas comemorativas brasileiras (mês, dia)
BR_HOLIDAYS = [
    (1, 1), (2, 14), (3, 8), (4, 21), (5, 1), (5, 12), (6, 12),
    (8, 11), (9, 7), (10, 12), (11, 2), (11, 15), (11, 25), (12, 25),
]

# ============================================================================
# PERFIS DE DEMANDA POR CATEGORIA (copiados de data_profiles.py)
# ============================================================================

CATEGORY_PROFILES: Dict[str, dict] = {
    "Tecidos e Revestimentos": {"mult": 0.08, "wknd": 1.15, "elast": 0.45, "season": 0.20, "zero": 0.05},
    "Estruturas de Madeira":   {"mult": 0.06, "wknd": 1.10, "elast": 0.35, "season": 0.25, "zero": 0.08},
    "Ferramentas e Insumos de Produção": {"mult": 0.10, "wknd": 0.85, "elast": 0.50, "season": 0.15, "zero": 0.02},
    "Colas e Adesivos":        {"mult": 0.12, "wknd": 0.90, "elast": 0.40, "season": 0.10, "zero": 0.01},
    "Espumas e Enchimentos":   {"mult": 0.07, "wknd": 1.20, "elast": 0.48, "season": 0.22, "zero": 0.06},
    "Acabamentos":             {"mult": 0.09, "wknd": 1.25, "elast": 0.42, "season": 0.18, "zero": 0.04},
    "Ferragens e Acessórios":  {"mult": 0.11, "wknd": 1.05, "elast": 0.45, "season": 0.12, "zero": 0.03},
}
DEFAULT_PROFILE = {"mult": 0.08, "wknd": 1.10, "elast": 0.45, "season": 0.15, "zero": 0.05}

# ============================================================================
# DADOS HARDCODED — Fornecedores realistas
# ============================================================================

FORNECEDORES_DATA = [
    # (nome, cep, lat, lon, confiabilidade, prazo_dias)
    ("Metalúrgica Central Ltda",         "01001-000", -23.5505, -46.6340, 0.97, 3),
    ("Elétrica Industrial SP",           "04578-000", -23.6105, -46.6940, 0.91, 5),
    ("Química do Brasil S.A.",           "13083-000", -22.9068, -47.0616, 0.93, 7),
    ("Distribuidora Express Log",        "80215-000", -25.4284, -49.2733, 0.82, 2),
    ("Importadora Técnica Nacional",     "20020-000", -22.9035, -43.2096, 0.87, 15),
    ("Madeireira Paraná EIRELI",         "83323-000", -25.5163, -49.1754, 0.94, 4),
    ("Têxtil Nordeste Ltda",             "50020-000", -8.0476,  -34.8770, 0.89, 8),
    ("Ferragens São Paulo Comércio",     "03015-000", -23.5290, -46.6191, 0.95, 2),
    ("Adesivos & Colas BR",             "09110-000", -23.6443, -46.5322, 0.96, 3),
    ("Espumas Sul Indústria",           "81200-000", -25.4372, -49.2700, 0.90, 6),
    ("Acabamentos Premium",              "01310-000", -23.5558, -46.6396, 0.88, 5),
    ("Insumos Gerais do Sudeste",        "30130-000", -19.9245, -43.9352, 0.85, 10),
]

# ============================================================================
# DADOS HARDCODED — Agentes IA
# ============================================================================

AGENTES_DATA = [
    ("Analisador de Demanda",              "Analisa histórico de vendas e prevê necessidade de estoque usando modelos ML.",         "active"),
    ("Otimizador de Compras",              "Compara fornecedores, negocia preços e recomenda a melhor opção de compra.",            "active"),
    ("Auditor de Risco",                   "Verifica saúde financeira do fornecedor, prazos e riscos de entrega.",                 "active"),
    ("Agente de Previsão de Preços",       "Analisa tendências de mercado e prevê flutuações de preços com séries temporais.",     "active"),
    ("Agente de Monitoramento de Estoque", "Monitora níveis de estoque em tempo real e dispara alertas antes da ruptura.",         "inactive"),
    ("Agente de Análise de Fornecedores",  "Avalia performance histórica de fornecedores e identifica oportunidades de economia.", "active"),
]

# ============================================================================
# DADOS HARDCODED — Usuários de demonstração
# ============================================================================

USERS_DATA = [
    # (email, full_name, role)
    ("admin@pmi.com.br",     "Carlos Mendonça",   "owner"),
    ("gerente@pmi.com.br",   "Fernanda Ribeiro",  "manager"),
    ("compras@pmi.com.br",   "Rafael Santos",     "operator"),
    ("estoque@pmi.com.br",   "Juliana Oliveira",  "operator"),
    ("viewer@pmi.com.br",    "Pedro Almeida",     "viewer"),
]


# ============================================================================
# FUNÇÕES AUXILIARES — Geração de séries temporais
# ============================================================================

def _is_weekend(dt: datetime) -> bool:
    return dt.weekday() >= 5


def _near_holiday(dt: datetime, tolerance: int = 5) -> bool:
    dt_naive = dt.replace(tzinfo=None) if dt.tzinfo else dt
    for m, d in BR_HOLIDAYS:
        try:
            holiday = datetime(dt_naive.year, m, d)
            if abs((dt_naive - holiday).days) <= tolerance:
                return True
        except ValueError:
            pass
    return False


def _price_base_for_product(produto_id: int, categoria: str) -> float:
    """Determina preço base realista por categoria."""
    rng = np.random.RandomState(producto_id_seed(produto_id))
    ranges = {
        "Tecidos e Revestimentos": (25.0, 350.0),
        "Estruturas de Madeira":   (15.0, 200.0),
        "Ferramentas e Insumos de Produção": (8.0, 500.0),
        "Colas e Adesivos":        (12.0, 180.0),
        "Espumas e Enchimentos":   (30.0, 400.0),
        "Acabamentos":             (5.0, 250.0),
        "Ferragens e Acessórios":  (2.0, 150.0),
    }
    lo, hi = ranges.get(categoria, (10.0, 300.0))
    return round(rng.uniform(lo, hi), 2)


def producto_id_seed(pid: int) -> int:
    """Seed determinístico por produto."""
    return RANDOM_SEED + pid * 7


def generate_price_series(
    produto_id: int,
    categoria: str,
    start: datetime,
    days: int,
) -> List[Tuple[datetime, float]]:
    """Random-walk realista de preços: tendência + sazonalidade + feriados + ruído."""
    rng = np.random.RandomState(producto_id_seed(produto_id))
    base = _price_base_for_product(produto_id, categoria)
    price = base
    series: List[Tuple[datetime, float]] = []

    for d in range(days):
        dt = start + timedelta(days=d)
        t = d / max(days, 1)

        trend = 1.0002                                       # +0.02%/dia (~7%/ano)
        annual = 0.015 * np.sin(2 * np.pi * t)              # ±1.5%
        weekend = rng.uniform(-0.005, 0.01) if _is_weekend(dt) else 0.0
        holiday = rng.uniform(0.02, 0.06) if _near_holiday(dt) else 0.0
        noise = rng.normal(0, 0.012)                         # ±1.2% σ

        price *= trend * (1 + annual) * (1 + weekend) * (1 + holiday) * (1 + noise)
        price = float(np.clip(price, base * 0.65, base * 1.55))
        series.append((dt, round(price, 2)))

    return series


def generate_sales_series(
    produto_id: int,
    categoria: str,
    estoque_minimo: int,
    price_series: List[Tuple[datetime, float]],
) -> List[Tuple[datetime, int, float]]:
    """Vendas correlacionadas com preço: elasticidade, sazonalidade, feriados."""
    rng = np.random.RandomState(producto_id_seed(produto_id) + 1000)
    prof = CATEGORY_PROFILES.get(categoria, DEFAULT_PROFILE)

    base_demand = max(estoque_minimo * prof["mult"], 0.25)
    avg_price = np.mean([p for _, p in price_series]) if price_series else 1.0
    sales: List[Tuple[datetime, int, float]] = []

    for dt, price in price_series:
        # Dia com zero vendas (probabilidade da categoria)
        if rng.random() < prof["zero"]:
            sales.append((dt, 0, 0.0))
            continue

        price_effect = 1 / ((price / avg_price) ** prof["elast"])
        wknd = prof["wknd"] if _is_weekend(dt) else 1.0
        hol_boost = rng.uniform(1.3, 1.8) if _near_holiday(dt) else 1.0
        day_of_year = dt.timetuple().tm_yday
        season = 1 + prof["season"] * np.sin(2 * np.pi * day_of_year / 365)
        noise = rng.uniform(0.7, 1.3)

        qty = int(round(base_demand * price_effect * wknd * hol_boost * season * noise))
        qty = max(qty, 0)
        revenue = round(qty * price, 2)
        sales.append((dt, qty, revenue))

    return sales


# ============================================================================
# ETAPAS DE SEED
# ============================================================================

def step_tenant(session: Session) -> UUID:
    """Cria ou reutiliza o Tenant padrão 'PMI Estofados'."""
    LOG.info("━━━ ETAPA 1/10 ━━━  Tenant")

    existing = session.exec(select(Tenant).where(Tenant.slug == "pmi-estofados")).first()
    if existing:
        LOG.info(f"  ✔ Tenant existente: {existing.nome} (id={existing.id})")
        return existing.id

    tenant = Tenant(
        nome="PMI Estofados Ltda",
        slug="pmi-estofados",
        plano="pro",
        ativo=True,
        max_usuarios=20,
        max_produtos=500,
        onboarding_completed=True,
    )
    session.add(tenant)
    session.flush()
    LOG.info(f"  ✔ Tenant criado: {tenant.nome} (id={tenant.id})")
    return tenant.id


def step_users(session: Session, tenant_id: UUID) -> List[User]:
    """Cria usuários de demonstração."""
    LOG.info("━━━ ETAPA 2/10 ━━━  Usuários")

    from passlib.context import CryptContext
    pwd_ctx = CryptContext(schemes=["argon2", "bcrypt"], deprecated="auto")
    hashed = pwd_ctx.hash(DEFAULT_PASSWORD)

    users: List[User] = []
    for email, name, role in USERS_DATA:
        existing = session.exec(select(User).where(User.email == email)).first()
        if existing:
            LOG.info(f"  ⏭ Usuário já existe: {email}")
            users.append(existing)
            continue
        u = User(
            email=email,
            hashed_password=hashed,
            full_name=name,
            is_active=True,
            role=role,
            email_verified=True,
            tenant_id=tenant_id,
        )
        session.add(u)
        users.append(u)
        LOG.info(f"  ✔ Usuário criado: {email} ({role})")

    session.flush()
    return users


def step_fornecedores(session: Session, tenant_id: UUID) -> List[Fornecedor]:
    """Cria fornecedores com dados realistas."""
    LOG.info("━━━ ETAPA 3/10 ━━━  Fornecedores")

    fornecs: List[Fornecedor] = []
    for nome, cep, lat, lon, conf, prazo in FORNECEDORES_DATA:
        existing = session.exec(
            select(Fornecedor).where(Fornecedor.nome == nome, Fornecedor.tenant_id == tenant_id)
        ).first()
        if existing:
            fornecs.append(existing)
            continue

        f = Fornecedor(
            nome=nome, cep=cep,
            latitude=lat, longitude=lon,
            confiabilidade=conf,
            prazo_entrega_dias=prazo,
            tenant_id=tenant_id,
        )
        session.add(f)
        fornecs.append(f)

    session.flush()
    LOG.info(f"  ✔ {len(fornecs)} fornecedores prontos")
    return fornecs


def step_produtos(session: Session, tenant_id: UUID) -> List[Produto]:
    """Carrega produtos do CSV ou hardcoded."""
    LOG.info("━━━ ETAPA 4/10 ━━━  Produtos (catálogo)")

    csv_path = PROJECT_ROOT / "data" / "products_seed.csv"
    rows: List[dict] = []

    if csv_path.exists():
        with open(csv_path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for r in reader:
                rows.append(r)
        LOG.info(f"  📂 CSV carregado: {len(rows)} produtos")
    else:
        LOG.info("  📦 CSV não encontrado, usando catálogo embutido")
        rows = _hardcoded_products()

    produtos: List[Produto] = []
    for row in rows:
        sku = str(row.get("sku", "")).strip()
        nome = str(row.get("nome", "")).strip()
        if not sku or not nome:
            continue

        existing = session.exec(select(Produto).where(Produto.sku == sku)).first()
        if existing:
            produtos.append(existing)
            continue

        p = Produto(
            nome=nome,
            sku=sku,
            categoria=str(row.get("categoria", "")).strip() or None,
            estoque_atual=int(row.get("estoque_atual", 0)),
            estoque_minimo=int(row.get("estoque_minimo", 0)),
            tenant_id=tenant_id,
        )
        session.add(p)
        produtos.append(p)

    session.flush()
    LOG.info(f"  ✔ {len(produtos)} produtos no catálogo")
    return produtos


def step_ofertas(
    session: Session,
    tenant_id: UUID,
    produtos: List[Produto],
    fornecedores: List[Fornecedor],
) -> int:
    """Cria ofertas de fornecedores para cada produto (mercado simulado)."""
    LOG.info("━━━ ETAPA 5/10 ━━━  Ofertas de Fornecedores")

    rng = random.Random(RANDOM_SEED)
    count = 0

    for p in produtos:
        # Cada produto recebe ofertas de 2 a 5 fornecedores
        n_fornecs = rng.randint(2, min(5, len(fornecedores)))
        selected = rng.sample(fornecedores, n_fornecs)
        base_price = _price_base_for_product(p.id or 1, p.categoria or "")

        for f in selected:
            existing = session.exec(
                select(OfertaProduto).where(
                    OfertaProduto.produto_id == p.id,
                    OfertaProduto.fornecedor_id == f.id,
                )
            ).first()
            if existing:
                continue

            variacao = Decimal(str(round(rng.uniform(0.85, 1.25), 4)))
            oferta = OfertaProduto(
                produto_id=p.id,
                fornecedor_id=f.id,
                preco_ofertado=Decimal(str(base_price)) * variacao,
                estoque_disponivel=rng.randint(50, 2000),
                validade_oferta=datetime.now(timezone.utc) + timedelta(days=rng.randint(30, 180)),
                tenant_id=tenant_id,
            )
            session.add(oferta)
            count += 1

    session.flush()
    LOG.info(f"  ✔ {count} ofertas criadas")
    return count


def step_historico_precos(
    session: Session,
    tenant_id: UUID,
    produtos: List[Produto],
    fornecedores: List[Fornecedor],
    days: int,
    only_missing: bool = False,
) -> int:
    """Gera histórico de preços com random-walk + sazonalidade."""
    LOG.info(f"━━━ ETAPA 6/10 ━━━  Histórico de Preços ({days} dias)")

    end_date = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    start_date = end_date - timedelta(days=days - 1)
    total = 0

    for idx, p in enumerate(produtos, 1):
        if idx % 10 == 0 or idx == len(produtos):
            LOG.info(f"  [{idx}/{len(produtos)}] Preços...")

        existing_dates: set = set()
        if only_missing:
            rows = session.exec(
                select(PrecosHistoricos.coletado_em).where(PrecosHistoricos.produto_id == p.id)
            ).all()
            existing_dates = {r.date() if hasattr(r, 'date') else r for r in rows}

        series = generate_price_series(p.id or idx, p.categoria or "", start_date, days)
        rng_f = random.Random(RANDOM_SEED + (p.id or idx))
        fornecedor_nome = rng_f.choice(fornecedores).nome if fornecedores else "Fornecedor Padrão"

        for dt, price in series:
            if only_missing and dt.date() in existing_dates:
                continue
            session.add(PrecosHistoricos(
                produto_id=p.id,
                fornecedor=fornecedor_nome,
                preco=Decimal(str(price)),
                moeda="BRL",
                coletado_em=dt,
                is_synthetic=True,
                tenant_id=tenant_id,
            ))
            total += 1

        # Commit por produto para evitar transação gigante
        if idx % 5 == 0:
            session.commit()

    session.commit()
    LOG.info(f"  ✔ {total:,} registros de preços criados")
    return total


def step_historico_vendas(
    session: Session,
    tenant_id: UUID,
    produtos: List[Produto],
    days: int,
    only_missing: bool = False,
) -> int:
    """Gera histórico de vendas correlacionado com preços."""
    LOG.info(f"━━━ ETAPA 7/10 ━━━  Histórico de Vendas ({days} dias)")

    end_date = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    start_date = end_date - timedelta(days=days - 1)
    total = 0

    for idx, p in enumerate(produtos, 1):
        if idx % 10 == 0 or idx == len(produtos):
            LOG.info(f"  [{idx}/{len(produtos)}] Vendas...")

        existing_dates: set = set()
        if only_missing:
            rows = session.exec(
                select(VendasHistoricas.data_venda).where(VendasHistoricas.produto_id == p.id)
            ).all()
            existing_dates = {r.date() if hasattr(r, 'date') else r for r in rows}

        # Gerar preços primeiro para correlacionar
        price_series = generate_price_series(p.id or idx, p.categoria or "", start_date, days)
        sales_series = generate_sales_series(
            p.id or idx, p.categoria or "", p.estoque_minimo or 50, price_series
        )

        for dt, qty, revenue in sales_series:
            if only_missing and dt.date() in existing_dates:
                continue
            session.add(VendasHistoricas(
                produto_id=p.id,
                data_venda=dt,
                quantidade=qty,
                receita=Decimal(str(revenue)),
                tenant_id=tenant_id,
            ))
            total += 1

        if idx % 5 == 0:
            session.commit()

    session.commit()
    LOG.info(f"  ✔ {total:,} registros de vendas criados")
    return total


def step_ordens(
    session: Session,
    tenant_id: UUID,
    produtos: List[Produto],
    fornecedores: List[Fornecedor],
) -> int:
    """Gera ordens de compra realistas dos últimos 30 dias."""
    LOG.info("━━━ ETAPA 8/10 ━━━  Ordens de Compra")

    rng = random.Random(RANDOM_SEED + 999)
    now = datetime.now(timezone.utc)
    count = 0

    # Simular ~40 ordens no último mês
    for _ in range(40):
        p = rng.choice(produtos)
        f = rng.choice(fornecedores)
        dias_atras = rng.randint(0, 30)
        data_criacao = now - timedelta(days=dias_atras, hours=rng.randint(0, 23))

        status = rng.choices(
            ["pending", "approved", "rejected", "cancelled"],
            weights=[30, 45, 15, 10],
        )[0]
        origem = rng.choices(["Automática", "Manual"], weights=[60, 40])[0]
        qtd = rng.randint(5, 200)
        base_price = _price_base_for_product(p.id or 1, p.categoria or "")
        valor = Decimal(str(round(qtd * base_price * rng.uniform(0.9, 1.15), 2)))

        # Autoridade baseada no valor
        nivel = 1 if valor < 5000 else (2 if valor < 20000 else 3)
        aprovador = None
        data_aprov = None
        justificativa = None

        if status == "approved":
            aprovador = rng.choice(["Carlos Mendonça", "Fernanda Ribeiro"])
            data_aprov = data_criacao + timedelta(hours=rng.randint(1, 48))
            justificativa = rng.choice([
                f"Reposição de estoque — {p.nome} abaixo do mínimo.",
                f"Aprovado com base na previsão de demanda para os próximos 30 dias.",
                f"Melhor preço identificado: {f.nome} (confiabilidade {f.confiabilidade:.0%}).",
                f"Urgência operacional — estoque zerado em {rng.randint(2,7)} dias.",
            ])
        elif status == "rejected":
            justificativa = rng.choice([
                "Preço acima da média de mercado em 15%.",
                "Fornecedor com histórico de atrasos recentes.",
                "Estoque ainda suficiente para os próximos 45 dias.",
                "Aguardando cotação de fornecedores alternativos.",
            ])

        ordem = OrdemDeCompra(
            produto_id=p.id,
            fornecedor_id=f.id,
            quantidade=qtd,
            valor=valor,
            status=status,
            origem=origem,
            autoridade_nivel=nivel,
            aprovado_por=aprovador,
            data_criacao=data_criacao,
            data_aprovacao=data_aprov,
            justificativa=justificativa,
            tenant_id=tenant_id,
        )
        session.add(ordem)
        count += 1

    session.flush()
    LOG.info(f"  ✔ {count} ordens de compra criadas")
    return count


def step_auditoria(
    session: Session,
    tenant_id: UUID,
    produtos: List[Produto],
    fornecedores: List[Fornecedor],
) -> int:
    """Gera trilha de auditoria de decisões dos agentes."""
    LOG.info("━━━ ETAPA 9/10 ━━━  Auditoria de Decisões")

    rng = random.Random(RANDOM_SEED + 2000)
    now = datetime.now(timezone.utc)
    count = 0

    acoes = [
        ("recommend_supplier", "Otimizador de Compras"),
        ("approve_order",      "Otimizador de Compras"),
        ("reject_purchase",    "Auditor de Risco"),
        ("demand_forecast",    "Analisador de Demanda"),
        ("price_alert",        "Agente de Previsão de Preços"),
        ("stock_alert",        "Agente de Monitoramento de Estoque"),
    ]

    for _ in range(60):
        p = rng.choice(produtos)
        f = rng.choice(fornecedores)
        acao, agente = rng.choice(acoes)
        dias_atras = rng.randint(0, 60)

        decisao_map = {
            "recommend_supplier": f'{{"supplier": "{f.nome}", "savings_pct": {rng.uniform(5,25):.1f}, "confidence": {rng.uniform(0.7,0.99):.2f}}}',
            "approve_order":     f'{{"status": "recommended", "amount": {rng.randint(500,15000)}, "priority": "{rng.choice(["high","medium","low"])}"}}',
            "reject_purchase":   f'{{"reason": "risk_score_high", "risk_score": {rng.uniform(0.6,0.95):.2f}, "supplier": "{f.nome}"}}',
            "demand_forecast":   f'{{"forecast_7d": {rng.randint(10,200)}, "forecast_30d": {rng.randint(50,800)}, "trend": "{rng.choice(["up","stable","down"])}"}}',
            "price_alert":       f'{{"current_price": {rng.uniform(10,500):.2f}, "predicted_change": {rng.uniform(-15,20):.1f}, "horizon": "7d"}}',
            "stock_alert":       f'{{"current_stock": {p.estoque_atual}, "min_stock": {p.estoque_minimo}, "days_until_zero": {rng.randint(1,14)}}}',
        }

        raciocinio_map = {
            "recommend_supplier": f"Análise de {len(fornecedores)} fornecedores para {p.nome}. {f.nome} oferece melhor relação preço/prazo com confiabilidade de {f.confiabilidade:.0%}.",
            "approve_order":     f"Estoque de {p.nome} ({p.estoque_atual} un.) abaixo do mínimo ({p.estoque_minimo} un.). Recomendada reposição imediata.",
            "reject_purchase":   f"Fornecedor {f.nome} apresenta risco elevado: prazo de {f.prazo_entrega_dias} dias e confiabilidade de {f.confiabilidade:.0%}.",
            "demand_forecast":   f"Modelo ARIMA prevê aumento de {rng.randint(5,30)}% na demanda de {p.nome} nos próximos 30 dias.",
            "price_alert":       f"Tendência de alta detectada para {p.nome}. Preço médio subiu {rng.uniform(2,12):.1f}% na última semana.",
            "stock_alert":       f"ALERTA: {p.nome} com estoque em {p.estoque_atual} un. — abaixo do mínimo de {p.estoque_minimo} un.",
        }

        audit = AuditoriaDecisao(
            agente_nome=agente,
            sku=p.sku,
            acao=acao,
            decisao=decisao_map[acao],
            raciocinio=raciocinio_map[acao],
            contexto=f"Produtos em catálogo: {len(produtos)} | Fornecedores ativos: {len(fornecedores)}",
            data_decisao=now - timedelta(days=dias_atras, hours=rng.randint(0, 23)),
            tenant_id=tenant_id,
        )
        session.add(audit)
        count += 1

    session.flush()
    LOG.info(f"  ✔ {count} registros de auditoria criados")
    return count


def step_agentes_e_chat(
    session: Session,
    tenant_id: UUID,
    produtos: List[Produto],
) -> None:
    """Cria agentes IA e sessão de chat de exemplo."""
    LOG.info("━━━ ETAPA 10/10 ━━━  Agentes & Chat Demo")

    # ── Agentes ──
    for nome, desc, status in AGENTES_DATA:
        existing = session.exec(
            select(Agente).where(Agente.nome == nome, Agente.tenant_id == tenant_id)
        ).first()
        if existing:
            continue
        session.add(Agente(
            nome=nome, descricao=desc, status=status, tenant_id=tenant_id,
        ))
    session.flush()
    LOG.info(f"  ✔ {len(AGENTES_DATA)} agentes configurados")

    # ── Chat Session de exemplo ──
    existing_chat = session.exec(select(ChatSession).where(ChatSession.tenant_id == tenant_id)).first()
    if existing_chat:
        LOG.info("  ⏭ Chat de demonstração já existe")
        return

    chat_session = ChatSession(tenant_id=tenant_id)
    session.add(chat_session)
    session.flush()

    p_example = produtos[0] if produtos else None
    messages = [
        ("human", "Qual o status do estoque atual?"),
        ("agent", f"Analisei o catálogo completo. Atualmente temos {len(produtos)} produtos cadastrados. "
                  f"{'O produto ' + p_example.nome + ' está com ' + str(p_example.estoque_atual) + ' unidades em estoque.' if p_example else 'Nenhum produto encontrado.'}"),
        ("human", "Quais produtos estão abaixo do estoque mínimo?"),
        ("agent", _generate_stock_alert_message(produtos)),
        ("human", "Recomende uma ordem de compra para os itens críticos."),
        ("agent", "Com base na análise de demanda e preço dos últimos 30 dias, recomendo as seguintes ordens:\n\n"
                  "1. **Reposição urgente** — produtos com estoque < 50% do mínimo\n"
                  "2. **Reposição preventiva** — produtos com tendência de alta na demanda\n\n"
                  "Deseja que eu crie as ordens automaticamente?"),
    ]

    for sender, content in messages:
        msg = ChatMessage(
            session_id=chat_session.id,
            sender=sender,
            content=content,
            tenant_id=tenant_id,
        )
        session.add(msg)

    session.flush()
    LOG.info(f"  ✔ Chat de demonstração criado ({len(messages)} mensagens)")


def _generate_stock_alert_message(produtos: List[Produto]) -> str:
    """Gera mensagem realista de alerta de estoque."""
    below_min = [p for p in produtos if p.estoque_atual < p.estoque_minimo]
    if not below_min:
        return "✅ Todos os produtos estão com estoque acima do mínimo. Nenhuma ação necessária no momento."

    lines = [f"⚠️ **{len(below_min)} produtos abaixo do estoque mínimo:**\n"]
    for p in below_min[:8]:
        pct = (p.estoque_atual / p.estoque_minimo * 100) if p.estoque_minimo > 0 else 0
        lines.append(f"• **{p.nome}** ({p.sku}): {p.estoque_atual}/{p.estoque_minimo} un. ({pct:.0f}%)")
    if len(below_min) > 8:
        lines.append(f"\n... e mais {len(below_min) - 8} produtos.")
    return "\n".join(lines)


# ============================================================================
# LIMPEZA DE DADOS (sem drop de schema)
# ============================================================================

def clear_business_data(session: Session) -> None:
    """Remove dados de negócio mantendo schema, tenants e usuários intactos."""
    LOG.info("🗑️  Limpando dados de negócio existentes...")

    # Ordem importa (foreign keys) — commit individual por tabela
    tables = [
        "chat_actions", "chat_context", "chat_messages", "chat_sessions",
        "auditoria_decisoes", "ordens_de_compra", "ofertas_produtos",
        "modelos_predicao", "modelos_globais",
        "vendas_historicas", "precos_historicos",
        "agentes", "fornecedores", "produtos",
    ]
    for table in tables:
        try:
            session.exec(text(f"SET SESSION innodb_lock_wait_timeout = 120"))
            session.exec(text(f"DELETE FROM {table}"))
            session.commit()
            LOG.info(f"  🧹 {table}")
        except Exception as e:
            session.rollback()
            LOG.warning(f"  ⚠️  {table}: {e}")
    LOG.info("  ✔ Limpeza concluída")


# ============================================================================
# CATÁLOGO HARDCODED (fallback se não houver CSV)
# ============================================================================

def _hardcoded_products() -> List[dict]:
    """Catálogo hardcoded de 20 produtos caso o CSV não exista."""
    return [
        {"nome": "Parafuso Sextavado M12x50",       "sku": "FER-001", "categoria": "Ferragens e Acessórios",              "estoque_atual": 500, "estoque_minimo": 200},
        {"nome": "Rolamento Autocompensador 6205",   "sku": "FER-002", "categoria": "Ferragens e Acessórios",              "estoque_atual": 25,  "estoque_minimo": 10},
        {"nome": "Tecido Jacquard Floral 1m",        "sku": "TEC-001", "categoria": "Tecidos e Revestimentos",             "estoque_atual": 180, "estoque_minimo": 80},
        {"nome": "Chenille Premium 2m",              "sku": "TEC-002", "categoria": "Tecidos e Revestimentos",             "estoque_atual": 95,  "estoque_minimo": 60},
        {"nome": "Suede Importado 1.5m",             "sku": "TEC-003", "categoria": "Tecidos e Revestimentos",             "estoque_atual": 120, "estoque_minimo": 50},
        {"nome": "Chapa MDF 18mm",                   "sku": "MAD-001", "categoria": "Estruturas de Madeira",               "estoque_atual": 200, "estoque_minimo": 80},
        {"nome": "Sarrafo de Pinus 5x2cm",           "sku": "MAD-002", "categoria": "Estruturas de Madeira",               "estoque_atual": 350, "estoque_minimo": 100},
        {"nome": "Cola de Contato Extra 1L",         "sku": "COL-001", "categoria": "Colas e Adesivos",                    "estoque_atual": 150, "estoque_minimo": 60},
        {"nome": "Cola Quente Bastão (kg)",          "sku": "COL-002", "categoria": "Colas e Adesivos",                    "estoque_atual": 45,  "estoque_minimo": 30},
        {"nome": "Cola Spray Permanente 500ml",      "sku": "COL-003", "categoria": "Colas e Adesivos",                    "estoque_atual": 80,  "estoque_minimo": 40},
        {"nome": "Espuma D33 Soft 1x2m",             "sku": "ESP-001", "categoria": "Espumas e Enchimentos",               "estoque_atual": 60,  "estoque_minimo": 30},
        {"nome": "Manta Acrílica 200g 1x1m",        "sku": "ESP-002", "categoria": "Espumas e Enchimentos",               "estoque_atual": 200, "estoque_minimo": 80},
        {"nome": "Fibra Siliconada Solta 1kg",       "sku": "ESP-003", "categoria": "Espumas e Enchimentos",               "estoque_atual": 100, "estoque_minimo": 50},
        {"nome": "Zíper Reforçado 60cm",             "sku": "ACA-001", "categoria": "Acabamentos",                         "estoque_atual": 300, "estoque_minimo": 120},
        {"nome": "Botão Encapado 20mm",              "sku": "ACA-002", "categoria": "Acabamentos",                         "estoque_atual": 500, "estoque_minimo": 200},
        {"nome": "Pesponto Decorativo Duplo",        "sku": "ACA-003", "categoria": "Acabamentos",                         "estoque_atual": 150, "estoque_minimo": 60},
        {"nome": "Grampeador Pneumático Industrial", "sku": "INS-001", "categoria": "Ferramentas e Insumos de Produção",   "estoque_atual": 8,   "estoque_minimo": 3},
        {"nome": "Pistola de Cola Quente 200W",      "sku": "INS-002", "categoria": "Ferramentas e Insumos de Produção",   "estoque_atual": 12,  "estoque_minimo": 5},
        {"nome": "Agulha Estofado Curva 10cm",       "sku": "INS-003", "categoria": "Ferramentas e Insumos de Produção",   "estoque_atual": 200, "estoque_minimo": 100},
        {"nome": "Rodízio Silicone 50mm (jogo)",     "sku": "FER-003", "categoria": "Ferragens e Acessórios",              "estoque_atual": 60,  "estoque_minimo": 40},
    ]


# ============================================================================
# MAIN — Orquestrador
# ============================================================================

def _update_seed(new_seed: int) -> None:
    """Atualiza o seed global de randomização."""
    global RANDOM_SEED
    RANDOM_SEED = new_seed
    np.random.seed(RANDOM_SEED)


def run_seed(days: int = DAYS_OF_HISTORY, clear: bool = False, only_missing: bool = False) -> dict:
    """Executa o seed completo."""
    t0 = time.time()

    print()
    print("=" * 72)
    print("  🏭  SEED COMPLETO — PMI Estofados — Dados Realistas")
    print("=" * 72)
    print(f"  Dias de histórico : {days}")
    print(f"  Limpar antes      : {'Sim' if clear else 'Não'}")
    print(f"  Apenas faltantes  : {'Sim' if only_missing else 'Não'}")
    print(f"  Hora de início    : {datetime.now().strftime('%H:%M:%S')}")
    print("=" * 72)
    print()

    stats: Dict[str, int] = {}

    with Session(engine) as session:
        # Aumentar timeout do MySQL para operações pesadas
        try:
            session.exec(text("SET SESSION innodb_lock_wait_timeout = 600"))
            session.exec(text("SET SESSION wait_timeout = 600"))
        except Exception:
            pass  # Pode falhar em SQLite (testes)

        if clear:
            clear_business_data(session)

        # ── Etapas em ordem de dependência ──
        tenant_id = step_tenant(session)
        session.commit()

        users = step_users(session, tenant_id)
        session.commit()
        stats["users"] = len(users)

        fornecedores = step_fornecedores(session, tenant_id)
        session.commit()
        stats["fornecedores"] = len(fornecedores)

        produtos = step_produtos(session, tenant_id)
        session.commit()
        stats["produtos"] = len(produtos)

        stats["ofertas"] = step_ofertas(session, tenant_id, produtos, fornecedores)
        session.commit()

        stats["precos"] = step_historico_precos(
            session, tenant_id, produtos, fornecedores, days, only_missing
        )

        stats["vendas"] = step_historico_vendas(
            session, tenant_id, produtos, days, only_missing
        )

        stats["ordens"] = step_ordens(session, tenant_id, produtos, fornecedores)
        session.commit()

        stats["auditoria"] = step_auditoria(session, tenant_id, produtos, fornecedores)
        session.commit()

        step_agentes_e_chat(session, tenant_id, produtos)
        session.commit()

    elapsed = time.time() - t0

    # ── Sumário Final ──
    print()
    print("=" * 72)
    print("  ✅  SEED COMPLETO — SUCESSO!")
    print("=" * 72)
    print(f"  Tempo total       : {elapsed:.1f}s")
    print(f"  Tenant            : PMI Estofados Ltda")
    print(f"  Usuários          : {stats.get('users', 0)}")
    print(f"  Fornecedores      : {stats.get('fornecedores', 0)}")
    print(f"  Produtos          : {stats.get('produtos', 0)}")
    print(f"  Ofertas           : {stats.get('ofertas', 0)}")
    print(f"  Preços históricos : {stats.get('precos', 0):,}")
    print(f"  Vendas históricas : {stats.get('vendas', 0):,}")
    print(f"  Ordens de compra  : {stats.get('ordens', 0)}")
    print(f"  Auditoria         : {stats.get('auditoria', 0)}")
    print("=" * 72)
    print()
    print("  📌 Credenciais de acesso:")
    print(f"     Email : admin@pmi.com.br")
    print(f"     Senha : {DEFAULT_PASSWORD}")
    print()

    return stats


def main():
    parser = argparse.ArgumentParser(
        description="Seed completo do banco de dados PMI com dados realistas.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemplos:
  # Seed completo (365 dias, sem apagar):
  python scripts/seed_full.py

  # Limpar dados antigos e re-popular:
  python scripts/seed_full.py --clear --days 365

  # Apenas complementar dias faltantes:
  python scripts/seed_full.py --only-missing

  # Histórico curto para teste rápido:
  python scripts/seed_full.py --clear --days 90
        """,
    )
    parser.add_argument("--days", type=int, default=DAYS_OF_HISTORY, help=f"Dias de histórico (padrão: {DAYS_OF_HISTORY})")
    parser.add_argument("--clear", action="store_true", help="Limpar dados de negócio antes de popular")
    parser.add_argument("--only-missing", action="store_true", help="Gerar apenas dados faltantes (não duplica)")
    parser.add_argument("--seed", type=int, default=RANDOM_SEED, help=f"Seed para reprodutibilidade (padrão: {RANDOM_SEED})")

    args = parser.parse_args()

    # Atualizar seed global se fornecido
    _update_seed(args.seed)

    result = run_seed(days=args.days, clear=args.clear, only_missing=args.only_missing)

    result = run_seed(days=args.days, clear=args.clear, only_missing=args.only_missing)

    if not result:
        sys.exit(1)


if __name__ == "__main__":
    main()
