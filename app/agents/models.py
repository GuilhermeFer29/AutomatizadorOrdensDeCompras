"""
Pydantic Models para Structured Outputs dos Agentes.

ARQUITETURA DE PRODUÇÃO:
========================
Este módulo define os schemas de resposta dos agentes usando Pydantic.
Isso garante validação automática e elimina a necessidade de parsing com Regex.

BENEFÍCIOS:
- Validação automática de tipos
- Documentação auto-gerada
- Compatibilidade com output_schema do Agno
- Erros claros quando o LLM retorna formato inválido

REFERÊNCIAS:
- Agno Structured Outputs: https://docs.agno.com/input-output/structured-output/agent
- Pydantic v2: https://docs.pydantic.dev/latest/
- Gemini Structured Output: https://ai.google.dev/gemini-api/docs/structured-output

Autor: Sistema PMI | Data: 2026-01-14
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

# ============================================================================
# ENUMS
# ============================================================================

class ConfidenceLevel(str, Enum):
    """Nível de confiança da análise."""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class PurchaseDecision(str, Enum):
    """Decisão de compra."""
    APPROVE = "approve"
    REJECT = "reject"
    MANUAL_REVIEW = "manual_review"


class PriceTrend(str, Enum):
    """Tendência de preço."""
    UP = "alta"
    DOWN = "baixa"
    STABLE = "estável"


# ============================================================================
# MODELOS DO ANALISTA DE DEMANDA
# ============================================================================

class DemandAnalysisOutput(BaseModel):
    """
    Output estruturado do Analista de Demanda.

    Usado como output_schema no Agno Agent.
    """
    need_restock: bool = Field(
        description="Se o produto precisa de reabastecimento"
    )
    justification: str = Field(
        description="Explicação detalhada baseada nos dados analisados"
    )
    confidence_level: ConfidenceLevel = Field(
        description="Nível de confiança da análise (high, medium, low)"
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "need_restock": True,
                "justification": "Estoque atual (45) está abaixo do mínimo (50). Demanda prevista é de 30 unidades/dia.",
                "confidence_level": "high"
            }
        }
    }


# ============================================================================
# MODELOS DO PESQUISADOR DE MERCADO
# ============================================================================

class SupplierOffer(BaseModel):
    """Uma oferta de fornecedor."""
    fornecedor: str = Field(description="Nome do fornecedor")
    preco: float = Field(ge=0, description="Preço unitário")
    confiabilidade: float = Field(ge=0, le=1, description="Score de confiabilidade (0-1)")
    prazo_entrega_dias: int = Field(ge=1, description="Prazo de entrega em dias")
    estoque_disponivel: int = Field(ge=0, description="Quantidade disponível")


class BestOffer(BaseModel):
    """Melhor oferta encontrada."""
    fornecedor: str
    preco: float


class MarketResearchOutput(BaseModel):
    """
    Output estruturado do Pesquisador de Mercado.
    """
    offers: list[SupplierOffer] = Field(
        default_factory=list,
        description="Lista de ofertas de fornecedores"
    )
    preco_medio: float | None = Field(
        default=None,
        description="Preço médio das ofertas"
    )
    melhor_oferta: BestOffer | None = Field(
        default=None,
        description="Melhor oferta encontrada"
    )
    tendencias_mercado: str = Field(
        default="",
        description="Resumo das tendências de mercado"
    )
    previsao_ml: PriceTrend = Field(
        default=PriceTrend.STABLE,
        description="Tendência de preço segundo ML"
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "offers": [
                    {
                        "fornecedor": "Fornecedor A",
                        "preco": 25.50,
                        "confiabilidade": 0.95,
                        "prazo_entrega_dias": 3,
                        "estoque_disponivel": 500
                    }
                ],
                "preco_medio": 27.30,
                "melhor_oferta": {"fornecedor": "Fornecedor A", "preco": 25.50},
                "tendencias_mercado": "Preços estáveis com leve tendência de alta",
                "previsao_ml": "alta"
            }
        }
    }


# ============================================================================
# MODELOS DO ANALISTA DE LOGÍSTICA
# ============================================================================

class SelectedOffer(BaseModel):
    """Oferta selecionada pelo analista de logística."""
    source: str = Field(description="Nome do fornecedor")
    price: float = Field(ge=0, description="Preço unitário")
    estimated_total_cost: float = Field(ge=0, description="Custo total estimado (com frete)")
    delivery_time_days: int = Field(ge=1, description="Prazo de entrega")


class LogisticsAnalysisOutput(BaseModel):
    """
    Output estruturado do Analista de Logística.
    """
    selected_offer: SelectedOffer | None = Field(
        default=None,
        description="Oferta selecionada como melhor opção"
    )
    analysis_notes: str = Field(
        default="",
        description="Detalhes sobre a decisão e trade-offs"
    )
    alternatives: list[str] = Field(
        default_factory=list,
        description="Lista de alternativas viáveis"
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "selected_offer": {
                    "source": "Fornecedor A",
                    "price": 25.50,
                    "estimated_total_cost": 28.00,
                    "delivery_time_days": 3
                },
                "analysis_notes": "Fornecedor A oferece melhor custo-benefício",
                "alternatives": ["Fornecedor B (preço +10%, prazo -1 dia)"]
            }
        }
    }


# ============================================================================
# MODELOS DO GERENTE DE COMPRAS (DECISÃO FINAL)
# ============================================================================

class PurchaseRecommendationOutput(BaseModel):
    """
    Output estruturado do Gerente de Compras (decisão final).

    Este é o modelo principal que consolida todas as análises.
    """
    decision: PurchaseDecision = Field(
        description="Decisão final: approve, reject ou manual_review"
    )
    supplier: str | None = Field(
        default=None,
        description="Nome do fornecedor recomendado"
    )
    price: float | None = Field(
        default=None,
        ge=0,
        description="Preço unitário acordado"
    )
    currency: str = Field(
        default="BRL",
        description="Moeda (ISO 4217)"
    )
    quantity_recommended: int = Field(
        ge=0,
        description="Quantidade recomendada para compra"
    )
    rationale: str = Field(
        description="Justificativa detalhada da decisão"
    )
    next_steps: list[str] = Field(
        default_factory=list,
        description="Lista de ações a serem tomadas"
    )
    risk_assessment: str = Field(
        default="",
        description="Avaliação de riscos da operação"
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "decision": "approve",
                "supplier": "Fornecedor A",
                "price": 25.50,
                "currency": "BRL",
                "quantity_recommended": 100,
                "rationale": "Estoque abaixo do mínimo, fornecedor confiável, preço competitivo",
                "next_steps": ["Emitir ordem de compra", "Notificar almoxarifado"],
                "risk_assessment": "Baixo - fornecedor com histórico positivo"
            }
        }
    }


# ============================================================================
# MODELO CONSOLIDADO (RESULTADO FINAL DA ANÁLISE)
# ============================================================================

class SupplyChainAnalysisResult(BaseModel):
    """
    Resultado consolidado da análise completa de Supply Chain.

    Usado como retorno final de run_supply_chain_analysis().
    """
    product_sku: str = Field(description="SKU do produto analisado")

    # Resultados de cada agente
    demand_analysis: DemandAnalysisOutput | None = Field(
        default=None,
        description="Análise de demanda"
    )
    market_research: MarketResearchOutput | None = Field(
        default=None,
        description="Pesquisa de mercado"
    )
    logistics_analysis: LogisticsAnalysisOutput | None = Field(
        default=None,
        description="Análise logística"
    )
    recommendation: PurchaseRecommendationOutput = Field(
        description="Recomendação final de compra"
    )

    # Metadados
    agent_name: str = Field(
        default="Supply Chain Team",
        description="Nome do time de agentes"
    )
    need_restock: bool = Field(
        default=False,
        description="Resumo: precisa repor?"
    )
    analysis_version: str = Field(
        default="2.0",
        description="Versão do algoritmo de análise"
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "product_sku": "MEC-001",
                "demand_analysis": {
                    "need_restock": True,
                    "justification": "Estoque baixo",
                    "confidence_level": "high"
                },
                "recommendation": {
                    "decision": "approve",
                    "supplier": "Fornecedor A",
                    "price": 25.50,
                    "currency": "BRL",
                    "quantity_recommended": 100,
                    "rationale": "Reposição necessária",
                    "next_steps": ["Criar ordem"],
                    "risk_assessment": "Baixo"
                },
                "agent_name": "Supply Chain Team",
                "need_restock": True,
                "analysis_version": "2.0"
            }
        }
    }


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    # Enums
    "ConfidenceLevel",
    "PurchaseDecision",
    "PriceTrend",

    # Models de agentes
    "DemandAnalysisOutput",
    "SupplierOffer",
    "BestOffer",
    "MarketResearchOutput",
    "SelectedOffer",
    "LogisticsAnalysisOutput",
    "PurchaseRecommendationOutput",

    # Resultado consolidado
    "SupplyChainAnalysisResult",
]
