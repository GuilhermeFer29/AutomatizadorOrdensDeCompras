"""Definição das ferramentas Agno para orquestrar os serviços existentes."""

from __future__ import annotations

import json
import os
from dataclasses import asdict
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Dict, List, Tuple
from agno.tools import Toolkit
from sqlmodel import Session, select
from app.core.database import engine
from app.ml.training import METADATA_PATH, predict_prices
from app.models.models import Produto
from app.services.geolocation_service import calculate_distance
from app.services.scraping_service import ScrapingOutcome, scrape_and_save_price

# Importação condicional do Tavily
try:
    from tavily import TavilyClient
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


class SupplyChainToolkit(Toolkit):
    """Toolkit com ferramentas para análise de cadeia de suprimentos."""
    
    def __init__(self):
        super().__init__(name="supply_chain_toolkit")
        self.register(self.lookup_product)
        self.register(self.load_demand_forecast)
        self.register(self.scrape_latest_price)
        self.register(self.compute_distance)
        
        # Adiciona Tavily (recomendado para buscas contextuais)
        if TAVILY_AVAILABLE and os.getenv("TAVILY_API_KEY"):
            self.register(self.tavily_search)
    
    def lookup_product(self, sku: str) -> str:
        """Recupera metadados cadastrados de um produto específico.

        Args:
            sku: O SKU único do produto.
        
        Returns:
            JSON com dados do produto (id, sku, nome, estoque_atual, estoque_minimo, categoria).
        """
        try:
            produto = _load_product_by_sku(sku)
            result = {
                "id": produto.id,
                "sku": produto.sku,
                "nome": produto.nome,
                "estoque_atual": produto.estoque_atual,
                "estoque_minimo": produto.estoque_minimo,
                "categoria": produto.categoria,
                "atualizado_em": produto.atualizado_em.isoformat() if produto.atualizado_em else None,
            }
            return json.dumps(result, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"error": str(e)})

    def load_demand_forecast(self, sku: str, horizon_days: int = DEFAULT_FORECAST_HORIZON) -> str:
        """Carrega previsões futuras usando o modelo global LightGBM.

        Args:
            sku: O SKU único do produto.
            horizon_days: Quantidade de dias futuros para a previsão de demanda (padrão: 14).
        
        Returns:
            JSON com a previsão de demanda.
        """
        try:
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

            result = {
                "produto_id": produto.id,
                "sku": produto.sku,
                "modelo": "LightGBM_Global",
                "treinado_em": trained_at,
                "metricas": metrics,
                "horizon_days": horizon_days,
                "forecast": forecast_payload,
            }
            return json.dumps(result, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"error": str(e)})

    def scrape_latest_price(self, sku: str) -> str:
        """Executa o scraping no Mercado Livre e persiste o último preço coletado.

        Args:
            sku: O SKU único do produto.
        
        Returns:
            JSON com resultado do scraping (preço, fornecedor, etc).
        """
        try:
            produto = _load_product_by_sku(sku)
            outcome = scrape_and_save_price(produto_id=produto.id)
            payload = _format_outcome(outcome)
            payload["produto_sku"] = produto.sku
            payload["produto_nome"] = produto.nome
            return json.dumps(payload, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"error": str(e)})

    def compute_distance(
        self,
        origem_lat: float,
        origem_lon: float,
        destino_lat: float,
        destino_lon: float,
    ) -> str:
        """Calcula a distância em quilômetros entre dois pares de coordenadas.

        Args:
            origem_lat: Latitude do ponto de origem.
            origem_lon: Longitude do ponto de origem.
            destino_lat: Latitude do ponto de destino.
            destino_lon: Longitude do ponto de destino.
        
        Returns:
            JSON com a distância calculada.
        """
        try:
            distance_km = calculate_distance(
                origem_lat,
                origem_lon,
                destino_lat,
                destino_lon,
            )

            result = {
                "origem": {"lat": origem_lat, "lon": origem_lon},
                "destino": {"lat": destino_lat, "lon": destino_lon},
                "distance_km": distance_km,
            }
            return json.dumps(result)
        except Exception as e:
            return json.dumps({"error": str(e)})
    
    def tavily_search(self, query: str) -> str:
        """Busca informações atualizadas na web sobre fornecedores, tendências de mercado.

        Args:
            query: Termo de busca.
        
        Returns:
            Resultados da busca na web.
        """
        try:
            api_key = os.getenv("TAVILY_API_KEY")
            if not api_key:
                return "Tavily API key não configurada."
            
            client = TavilyClient(api_key=api_key)
            response = client.search(query, max_results=3)
            
            results = []
            for result in response.get("results", []):
                results.append({
                    "title": result.get("title"),
                    "url": result.get("url"),
                    "content": result.get("content", "")[:300]
                })
            
            return json.dumps(results, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"error": str(e)})


# Funções auxiliares mantidas para compatibilidade
def lookup_product(sku: str) -> Dict[str, Any]:
    """Função auxiliar para compatibilidade - usa o toolkit."""
    toolkit = SupplyChainToolkit()
    result_str = toolkit.lookup_product(sku)
    return json.loads(result_str)


def load_demand_forecast(sku: str, horizon_days: int = DEFAULT_FORECAST_HORIZON) -> Dict[str, Any]:
    """Função auxiliar para compatibilidade - usa o toolkit."""
    toolkit = SupplyChainToolkit()
    result_str = toolkit.load_demand_forecast(sku, horizon_days)
    return json.loads(result_str)
