"""
Definição das ferramentas Agno para orquestrar os serviços existentes.

ARQUITETURA HÍBRIDA (2025-10-14):
===================================
✅ ProductCatalogTool: Ferramenta RAG para consultas naturais ao catálogo
✅ SupplyChainToolkit: Ferramentas especializadas para análise de supply chain
✅ Integração: Agno (orquestração) + LangChain (RAG) + Google AI (LLM/embeddings)
"""

from __future__ import annotations

import json
import os
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Dict, List, Tuple
from agno.tools import Toolkit
from sqlmodel import Session, select
from app.core.database import engine
from app.ml.prediction import predict_prices_for_product
from app.ml.model_manager import list_trained_models, get_model_info
from app.models.models import Produto
from app.services.geolocation_service import calculate_distance
from app.services.rag_service import query_product_catalog_with_google_rag

# Importação condicional do Tavily
try:
    from tavily import TavilyClient
    TAVILY_AVAILABLE = True
except ImportError:
    TAVILY_AVAILABLE = False

ROOT_DIR = Path(__file__).resolve().parents[2]
DEFAULT_FORECAST_HORIZON = 14


# ============================================================================
# PRODUCT CATALOG TOOL - Ponte entre Agno e LangChain RAG
# ============================================================================

class ProductCatalogTool(Toolkit):
    """
    Ferramenta especialista em buscar informações sobre produtos no estoque.
    
    Esta ferramenta é a ponte entre o Agno Agent e o serviço RAG baseado em LangChain.
    Use-a sempre que a conversa mencionar produtos, seja por nome, SKU ou características,
    para verificar estoque, detalhes ou categorias.
    
    QUANDO USAR:
    - Perguntas sobre produtos específicos (por nome ou SKU)
    - Consultas de estoque e disponibilidade
    - Informações sobre categorias de produtos
    - Verificação de detalhes técnicos
    
    ARQUITETURA:
    - Input: Pergunta do usuário em linguagem natural
    - Processamento: LangChain RAG com embeddings Google AI
    - Output: Resposta contextualizada baseada no catálogo
    """
    
    def __init__(self):
        super().__init__(name="product_catalog")
        self.register(self.get_product_info)
    
    def get_product_info(self, user_question: str) -> str:
        """
        Busca informações detalhadas sobre produtos para responder a pergunta do usuário.
        
        Esta ferramenta usa RAG (Retrieval Augmented Generation) para encontrar
        produtos relevantes no catálogo e gerar uma resposta precisa e contextual.
        
        Args:
            user_question: A pergunta original e completa do usuário sobre o produto.
                          Exemplos:
                          - "Tem a parafusadeira Makita no estoque?"
                          - "Qual o SKU da serra circular?"
                          - "Quantas furadeiras temos disponíveis?"
                          - "Me fale sobre os produtos da categoria ferramentas elétricas"
        
        Returns:
            str: Resposta detalhada e contextualizada sobre o produto, incluindo
                 informações de estoque, SKU, categoria e outras características
                 encontradas no catálogo.
        
        Example:
            >>> tool = ProductCatalogTool()
            >>> tool.get_product_info("Qual o estoque da parafusadeira Bosch?")
            "A Parafusadeira Bosch GSR 12V (SKU_003) possui atualmente 28 unidades..."
        """
        try:
            print(f"🔧 [Product Catalog Tool] Buscando informações para: '{user_question}'")
            
            # Chama o serviço RAG que usa LangChain + Google AI
            response = query_product_catalog_with_google_rag(user_question)
            
            print(f"✅ [Product Catalog Tool] Resposta obtida ({len(response)} chars)")
            return response
            
        except Exception as e:
            error_msg = f"Desculpe, encontrei um erro ao buscar informações: {str(e)}"
            print(f"❌ [Product Catalog Tool] Erro: {e}")
            return error_msg


# ============================================================================
# SUPPLY CHAIN TOOLKIT - Ferramentas especializadas
# ============================================================================

def _load_product_by_sku(sku: str) -> Produto:
    with Session(engine) as session:
        produto = session.exec(select(Produto).where(Produto.sku == sku)).first()
        if not produto:
            raise ValueError(f"Produto com SKU '{sku}' não encontrado.")
        session.expunge(produto)
        return produto


def _load_product_metadata(sku: str) -> Tuple[Dict[str, float], str | None]:
    """Carrega metadados do modelo de um produto específico."""
    try:
        model_info = get_model_info(sku)
        if not model_info.get("exists"):
            return {}, None
        
        metrics = model_info.get("metrics", {})
        trained_at = model_info.get("trained_at")
        return metrics, trained_at
    except Exception:
        return {}, None


class SupplyChainToolkit(Toolkit):
    """Toolkit com ferramentas para análise de cadeia de suprimentos."""
    
    def __init__(self):
        super().__init__(name="supply_chain_toolkit")
        self.register(self.lookup_product)
        self.register(self.load_demand_forecast)
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
            result = predict_prices_for_product(sku=produto.sku, days_ahead=horizon_days)
            
            if "error" in result:
                return json.dumps({"error": result["error"]})
            
            values = result.get("prices", [])
            dates = result.get("dates", [])
            
            forecast_payload = [
                {
                    "date": date_str,
                    "predicted": float(price),
                }
                for date_str, price in zip(dates, values)
            ]

            metrics, trained_at = _load_product_metadata(sku)

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
