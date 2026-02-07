"""
Definicao de Planos de Assinatura SaaS.

Define os planos disponiveis para tenants, seus limites e features.
Os planos sao definidos em codigo (nao no banco) para simplicidade
e consistencia entre deploys.

Autor: Sistema PMI | Data: 2026-02-06
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Plan:
    """Definicao de um plano de assinatura."""
    slug: str
    nome: str
    preco_mensal_brl: float
    max_usuarios: int  # -1 = ilimitado
    max_produtos: int  # -1 = ilimitado
    ai_calls_mes: int  # -1 = ilimitado
    max_ordens_mes: int  # -1 = ilimitado
    features: list[str] = field(default_factory=list)
    destaque: bool = False  # Plano recomendado (highlight no frontend)


# ============================================================================
# PLANOS DISPONIVEIS
# ============================================================================

PLANS: dict[str, Plan] = {
    "free": Plan(
        slug="free",
        nome="Gratuito",
        preco_mensal_brl=0,
        max_usuarios=2,
        max_produtos=50,
        ai_calls_mes=100,
        max_ordens_mes=20,
        features=[
            "Dashboard basico",
            "Chat com IA (limitado)",
            "Gestao de estoque",
            "1 fornecedor",
        ],
    ),
    "starter": Plan(
        slug="starter",
        nome="Starter",
        preco_mensal_brl=197,
        max_usuarios=5,
        max_produtos=500,
        ai_calls_mes=1_000,
        max_ordens_mes=200,
        features=[
            "Tudo do Gratuito",
            "Previsao de demanda (ML)",
            "Pesquisa de precos",
            "Ate 10 fornecedores",
            "Relatorios basicos",
            "Suporte por email",
        ],
    ),
    "pro": Plan(
        slug="pro",
        nome="Profissional",
        preco_mensal_brl=497,
        max_usuarios=20,
        max_produtos=5_000,
        ai_calls_mes=10_000,
        max_ordens_mes=2_000,
        destaque=True,
        features=[
            "Tudo do Starter",
            "Agentes autonomos de compra",
            "Auditoria completa",
            "Fornecedores ilimitados",
            "API de integracao (ERP)",
            "Relatorios avancados",
            "Suporte prioritario",
        ],
    ),
    "enterprise": Plan(
        slug="enterprise",
        nome="Enterprise",
        preco_mensal_brl=0,  # Preco sob consulta
        max_usuarios=-1,
        max_produtos=-1,
        ai_calls_mes=-1,
        max_ordens_mes=-1,
        features=[
            "Tudo do Profissional",
            "Usuarios ilimitados",
            "SLA garantido",
            "Ambiente dedicado",
            "Onboarding personalizado",
            "Suporte 24/7",
            "Customizacoes sob demanda",
        ],
    ),
}


# ============================================================================
# HELPERS
# ============================================================================

def get_plan(slug: str) -> Plan | None:
    """Retorna um plano pelo slug."""
    return PLANS.get(slug)


def get_plan_limits(slug: str) -> dict:
    """Retorna os limites de um plano como dict."""
    plan = get_plan(slug)
    if not plan:
        plan = PLANS["free"]

    return {
        "max_usuarios": plan.max_usuarios,
        "max_produtos": plan.max_produtos,
        "ai_calls_mes": plan.ai_calls_mes,
        "max_ordens_mes": plan.max_ordens_mes,
    }


def get_all_plans() -> list[dict]:
    """Retorna todos os planos formatados para o frontend."""
    result = []
    for plan in PLANS.values():
        result.append({
            "slug": plan.slug,
            "nome": plan.nome,
            "preco_mensal_brl": plan.preco_mensal_brl,
            "max_usuarios": plan.max_usuarios,
            "max_produtos": plan.max_produtos,
            "ai_calls_mes": plan.ai_calls_mes,
            "max_ordens_mes": plan.max_ordens_mes,
            "features": plan.features,
            "destaque": plan.destaque,
        })
    return result


def is_within_limit(current: int, limit: int) -> bool:
    """Verifica se valor atual esta dentro do limite (-1 = ilimitado)."""
    if limit == -1:
        return True
    return current < limit
