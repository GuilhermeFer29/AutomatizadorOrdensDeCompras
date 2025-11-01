#!/usr/bin/env python3
"""
Perfis de Demanda por Categoria - Núcleo de Geração Realista

Define padrões realistas de demanda para cada categoria, eliminando
o gargalo de demanda fixa (max(..., 5)).
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class DemandProfile:
    """Perfil de demanda para uma categoria."""
    category: str
    base_multiplier: float  # estoque_min * multiplier = demanda base
    weekend_factor: float   # 1.0 = sem variação, 1.4 = +40%
    price_elasticity: float # -0.5 = demanda cai 0.5% por 1% aumento preço
    seasonality_amplitude: float  # 0-1: amplitude de sazonalidade
    zero_day_probability: float   # 0-1: probabilidade de dia com 0 vendas


CATEGORY_PROFILES = {
    "Tecidos e Revestimentos": DemandProfile(
        category="Tecidos e Revestimentos",
        base_multiplier=0.08,
        weekend_factor=1.15,
        price_elasticity=-0.45,
        seasonality_amplitude=0.20,
        zero_day_probability=0.05,
    ),
    "Estruturas de Madeira": DemandProfile(
        category="Estruturas de Madeira",
        base_multiplier=0.06,
        weekend_factor=1.10,
        price_elasticity=-0.35,
        seasonality_amplitude=0.25,
        zero_day_probability=0.08,
    ),
    "Ferramentas e Insumos de Produção": DemandProfile(
        category="Ferramentas e Insumos de Produção",
        base_multiplier=0.10,
        weekend_factor=0.85,
        price_elasticity=-0.50,
        seasonality_amplitude=0.15,
        zero_day_probability=0.02,
    ),
    "Colas e Adesivos": DemandProfile(
        category="Colas e Adesivos",
        base_multiplier=0.12,
        weekend_factor=0.90,
        price_elasticity=-0.40,
        seasonality_amplitude=0.10,
        zero_day_probability=0.01,
    ),
    "Espumas e Enchimentos": DemandProfile(
        category="Espumas e Enchimentos",
        base_multiplier=0.07,
        weekend_factor=1.20,
        price_elasticity=-0.48,
        seasonality_amplitude=0.22,
        zero_day_probability=0.06,
    ),
    "Acabamentos": DemandProfile(
        category="Acabamentos",
        base_multiplier=0.09,
        weekend_factor=1.25,
        price_elasticity=-0.42,
        seasonality_amplitude=0.18,
        zero_day_probability=0.04,
    ),
    "Ferragens e Acessórios": DemandProfile(
        category="Ferragens e Acessórios",
        base_multiplier=0.11,
        weekend_factor=1.05,
        price_elasticity=-0.45,
        seasonality_amplitude=0.12,
        zero_day_probability=0.03,
    ),
}

DEFAULT_PROFILE = DemandProfile(
    category="Desconhecido",
    base_multiplier=0.08,
    weekend_factor=1.10,
    price_elasticity=-0.45,
    seasonality_amplitude=0.15,
    zero_day_probability=0.05,
)


def get_profile_for_category(category: Optional[str]) -> DemandProfile:
    """Retorna perfil para categoria (case-insensitive)."""
    if not category:
        return DEFAULT_PROFILE
    
    normalized = category.strip()
    for cat_name, profile in CATEGORY_PROFILES.items():
        if cat_name.lower() == normalized.lower():
            return profile
    
    return DEFAULT_PROFILE


def estimate_daily_base_demand(
    estoque_minimo: int,
    category: Optional[str] = None
) -> float:
    """
    Estima demanda diária base.
    IMPORTANTE: Usa max(raw, 0.25) - não max(..., 5)
    """
    profile = get_profile_for_category(category)
    raw_demand = estoque_minimo * profile.base_multiplier
    return max(raw_demand, 0.25)  # 1 venda a cada 4 dias mínimo
