"""Definição das ferramentas LangChain para orquestrar os serviços existentes."""

from __future__ import annotations

import json
import os
from dataclasses import asdict
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Dict, List, Tuple

from langchain.tools import StructuredTool
from langchain_community.tools import WikipediaQueryRun
from langchain_community.utilities import WikipediaAPIWrapper
from langchain_experimental.tools import PythonAstREPLTool
from sqlmodel import Session, select

from app.core.database import engine
from app.ml.training import METADATA_PATH, predict_prices
from app.models.models import Produto
from app.services.geolocation_service import calculate_distance
from app.services.scraping_service import ScrapingOutcome, scrape_and_save_price

# Importação condicional do Tavily
try:
    from langchain_community.tools.tavily_search import TavilySearchResults
    TAVILY_AVAILABLE = True
except ImportError:
    TAVILY_AVAILABLE = False

ROOT_DIR = Path(__file__).resolve().parents[2]
DEFAULT_FORECAST_HORIZON = 14




def _format_outcome(outcome: ScrapingOutcome) -> Dict[str, Any]:
    payload = asdict(outcome)
    payload["price"] = float(payload["price"]) if payload.get("price") is not None else None
    return payload


def _load_product_by_sku(sku: str) -> Produto:
    with Session(engine) as session:
        produto = session.exec(select(Produto).where(Produto.sku == sku)).first()
        if not produto:
            raise ValueError(f"Produto com SKU '{sku}' não encontrado.")
        session.expunge(produto)
        return produto


def _load_global_metadata() -> Tuple[Dict[str, float], str | None]:
    if not METADATA_PATH.is_file():
        return {}, None

    try:
        payload = json.loads(METADATA_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}, None

    metrics = {key: float(value) for key, value in (payload.get("metrics", {}) or {}).items()}
    return metrics, payload.get("trained_at")


def lookup_product(sku: str) -> Dict[str, Any]:
    """Recupera metadados cadastrados de um produto específico.

    Args:
        sku: O SKU único do produto.
    """

    produto = _load_product_by_sku(sku)
    return {
        "id": produto.id,
        "sku": produto.sku,
        "nome": produto.nome,
        "estoque_atual": produto.estoque_atual,
        "estoque_minimo": produto.estoque_minimo,
        "categoria": produto.categoria,
        "atualizado_em": produto.atualizado_em.isoformat() if produto.atualizado_em else None,
    }


def load_demand_forecast(sku: str, horizon_days: int = DEFAULT_FORECAST_HORIZON) -> Dict[str, Any]:
    """Carrega previsões futuras usando o modelo global LightGBM.

    Args:
        sku: O SKU único do produto.
        horizon_days: Quantidade de dias futuros para a previsão de demanda (padrão: 14).
    """

    produto = _load_product_by_sku(sku)
    predictions = predict_prices(skus=[produto.sku], horizon_days=horizon_days)
    values = predictions.get(produto.sku, [])

    start_date = date.today() + timedelta(days=1)
    forecast_payload = [
        {
            "date": (start_date + timedelta(days=index)).strftime("%Y-%m-%d"),
            "predicted": float(price),
        }
        for index, price in enumerate(values)
    ]

    metrics, trained_at = _load_global_metadata()

    return {
        "produto_id": produto.id,
        "sku": produto.sku,
        "modelo": "LightGBM_Global",
        "treinado_em": trained_at,
        "metricas": metrics,
        "horizon_days": horizon_days,
        "forecast": forecast_payload,
    }


def scrape_latest_price(sku: str) -> Dict[str, Any]:
    """Executa o scraping no Mercado Livre e persiste o último preço coletado.

    Args:
        sku: O SKU único do produto.
    """

    produto = _load_product_by_sku(sku)
    outcome = scrape_and_save_price(produto_id=produto.id)
    payload = _format_outcome(outcome)
    payload["produto_sku"] = produto.sku
    payload["produto_nome"] = produto.nome
    return payload


def compute_distance(
    origem_lat: float,
    origem_lon: float,
    destino_lat: float,
    destino_lon: float,
) -> Dict[str, Any]:
    """Calcula a distância em quilômetros entre dois pares de coordenadas.

    Args:
        origem_lat: Latitude do ponto de origem.
        origem_lon: Longitude do ponto de origem.
        destino_lat: Latitude do ponto de destino.
        destino_lon: Longitude do ponto de destino.
    """

    distance_km = calculate_distance(
        origem_lat,
        origem_lon,
        destino_lat,
        destino_lon,
    )

    return {
        "origem": {"lat": origem_lat, "lon": origem_lon},
        "destino": {"lat": destino_lat, "lon": destino_lon},
        "distance_km": distance_km,
    }


# Ferramenta de busca na web Tavily (opcional, requer API key)
def _build_tavily_tool():
    if not TAVILY_AVAILABLE:
        return None
    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key:
        return None
    return TavilySearchResults(
        max_results=3,
        description=(
            "Busca informações atualizadas na web sobre fornecedores, tendências de mercado, "
            "notícias de produtos ou qualquer outro contexto relevante para decisões de compra."
        )
    )

# Ferramenta Wikipedia
wikipedia_tool = WikipediaQueryRun(
    api_wrapper=WikipediaAPIWrapper(
        top_k_results=2,
        doc_content_chars_max=2000,
    ),
    description=(
        "Busca informações enciclopédicas sobre produtos, componentes, materiais ou conceitos "
        "de mercado que podem ajudar na análise de fornecedores e preços."
    )
)

# Ferramenta Python REPL (para análise estatística)
python_repl_tool = PythonAstREPLTool(
    name="python_repl_ast",
    description=(
        "Executa código Python para análise de dados estatísticos. "
        "Útil para calcular médias móveis, tendências, correlações ou outras métricas "
        "que ajudem na tomada de decisão. Use quando precisar de cálculos complexos."
    )
)

# Montagem da lista de ferramentas
SUPPLY_CHAIN_TOOLS: List[StructuredTool] = [
    StructuredTool.from_function(
        func=lookup_product,
        name="lookup_product",
        description="Retorna dados de catálogo e estoque para um SKU específico.",
    ),
    StructuredTool.from_function(
        func=load_demand_forecast,
        name="load_demand_forecast",
        description="Carrega a projeção de demanda diária usando o modelo global LightGBM.",
    ),
    StructuredTool.from_function(
        func=scrape_latest_price,
        name="scrape_latest_price",
        description="Realiza scraping no Mercado Livre para obter o preço atual de um SKU.",
    ),
    StructuredTool.from_function(
        func=compute_distance,
        name="compute_distance",
        description="Calcula a distância geográfica entre dois pontos.",
    ),
    wikipedia_tool,
    python_repl_tool,
]

# Adiciona Tavily se disponível
_tavily = _build_tavily_tool()
if _tavily:
    SUPPLY_CHAIN_TOOLS.append(_tavily)
