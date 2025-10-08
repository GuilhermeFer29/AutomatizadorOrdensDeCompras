"""Definição das ferramentas LangChain para orquestrar os serviços existentes."""

from __future__ import annotations

import pickle
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd
from langchain.pydantic_v1 import BaseModel, Field
from langchain.tools import StructuredTool
from prophet import Prophet
from sqlmodel import Session, select

from app.core.database import engine
from app.models.models import ModeloPredicao, Produto
from app.services.geolocation_service import calculate_distance
from app.services.scraping_service import ScrapingOutcome, scrape_and_save_price

ROOT_DIR = Path(__file__).resolve().parents[2]
DEFAULT_FORECAST_HORIZON = 14


class ProdutoArgs(BaseModel):
    sku: str = Field(..., description="SKU único do produto")


class ForecastArgs(ProdutoArgs):
    horizon_days: int = Field(
        DEFAULT_FORECAST_HORIZON,
        ge=1,
        le=60,
        description="Quantidade de dias futuros para a previsão de demanda",
    )


class ScrapingArgs(ProdutoArgs):
    pass


class DistanceArgs(BaseModel):
    origem_lat: float = Field(..., description="Latitude do ponto de origem")
    origem_lon: float = Field(..., description="Longitude do ponto de origem")
    destino_lat: float = Field(..., description="Latitude do ponto de destino")
    destino_lon: float = Field(..., description="Longitude do ponto de destino")


def _resolve_artifact_path(path_str: str) -> Path:
    path = Path(path_str)
    if not path.is_absolute():
        return ROOT_DIR / path
    return path


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


def _latest_model_metadata(produto_id: int) -> ModeloPredicao | None:
    with Session(engine) as session:
        metadata = (
            session.exec(
                select(ModeloPredicao)
                .where(ModeloPredicao.produto_id == produto_id)
                .order_by(ModeloPredicao.treinado_em.desc())
            ).first()
        )
        if metadata:
            session.expunge(metadata)
        return metadata


def _load_forecast_dataframe(model_path: Path, horizon_days: int) -> pd.DataFrame:
    with model_path.open("rb") as artifact:
        model: Prophet = pickle.load(artifact)

    future = model.make_future_dataframe(periods=horizon_days, freq="D")
    forecast = model.predict(future)
    return forecast.tail(horizon_days)[["ds", "yhat", "yhat_lower", "yhat_upper"]]


def lookup_product(args: ProdutoArgs) -> Dict[str, Any]:
    """Recupera metadados cadastrados de um produto específico."""

    produto = _load_product_by_sku(args.sku)
    return {
        "id": produto.id,
        "sku": produto.sku,
        "nome": produto.nome,
        "estoque_atual": produto.estoque_atual,
        "estoque_minimo": produto.estoque_minimo,
        "categoria": produto.categoria,
        "atualizado_em": produto.atualizado_em.isoformat() if produto.atualizado_em else None,
    }


def load_demand_forecast(args: ForecastArgs) -> Dict[str, Any]:
    """Carrega a previsão de demanda futura para o produto via modelo Prophet."""

    produto = _load_product_by_sku(args.sku)
    metadata = _latest_model_metadata(produto.id)
    if not metadata:
        raise ValueError(
            "Nenhum modelo de previsão encontrado para o produto informado. Execute um treinamento antes."
        )

    model_path = _resolve_artifact_path(metadata.caminho_modelo)
    if not model_path.exists():
        raise FileNotFoundError(
            f"Modelo Prophet não encontrado em '{model_path}'. Treine novamente para gerar o artefato."
        )

    forecast_df = _load_forecast_dataframe(model_path, args.horizon_days)
    forecast_payload: List[Dict[str, Any]] = []
    for row in forecast_df.itertuples(index=False):
        forecast_payload.append(
            {
                "date": row.ds.strftime("%Y-%m-%d"),
                "predicted": float(row.yhat),
                "lower": float(row.yhat_lower),
                "upper": float(row.yhat_upper),
            }
        )

    metricas = {chave: float(valor) for chave, valor in (metadata.metricas or {}).items()}

    return {
        "produto_id": produto.id,
        "sku": produto.sku,
        "modelo": metadata.modelo_tipo,
        "treinado_em": metadata.treinado_em.isoformat() if metadata.treinado_em else None,
        "metricas": metricas,
        "horizon_days": args.horizon_days,
        "forecast": forecast_payload,
    }


def scrape_latest_price(args: ScrapingArgs) -> Dict[str, Any]:
    """Executa o scraping no Mercado Livre e persiste o último preço coletado."""

    produto = _load_product_by_sku(args.sku)
    outcome = scrape_and_save_price(produto_id=produto.id)
    payload = _format_outcome(outcome)
    payload["produto_sku"] = produto.sku
    payload["produto_nome"] = produto.nome
    return payload


def compute_distance(args: DistanceArgs) -> Dict[str, Any]:
    """Calcula a distância em quilômetros entre dois pares de coordenadas."""

    distance_km = calculate_distance(
        args.origem_lat,
        args.origem_lon,
        args.destino_lat,
        args.destino_lon,
    )

    return {
        "origem": {"lat": args.origem_lat, "lon": args.origem_lon},
        "destino": {"lat": args.destino_lat, "lon": args.destino_lon},
        "distance_km": distance_km,
    }


SUPPLY_CHAIN_TOOLS: List[StructuredTool] = [
    StructuredTool.from_function(
        func=lookup_product,
        name="lookup_product",
        description=(
            "Retorna dados de catálogo e estoque para um SKU específico. "
            "Use antes de tomar decisões de reposição."
        ),
        args_schema=ProdutoArgs,
    ),
    StructuredTool.from_function(
        func=load_demand_forecast,
        name="load_demand_forecast",
        description=(
            "Carrega a projeção de demanda diária baseada no último modelo Prophet do produto. "
            "Retorna a série prevista em JSON."
        ),
        args_schema=ForecastArgs,
    ),
    StructuredTool.from_function(
        func=scrape_latest_price,
        name="scrape_latest_price",
        description=(
            "Realiza scraping no Mercado Livre para obter o preço atual de um SKU e persiste o histórico."
        ),
        args_schema=ScrapingArgs,
    ),
    StructuredTool.from_function(
        func=compute_distance,
        name="compute_distance",
        description=(
            "Calcula a distância geográfica entre dois pontos (origem e destino) usando Haversine."
        ),
        args_schema=DistanceArgs,
    ),
]
