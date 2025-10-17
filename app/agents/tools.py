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
from app.models.models import Produto, OfertaProduto, Fornecedor, VendasHistoricas
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
    - VENDAS HISTÓRICAS E ANÁLISES
    
    ARQUITETURA:
    - Input: Pergunta do usuário em linguagem natural
    - Processamento: LangChain RAG com embeddings Google AI + SQL para vendas
    - Output: Resposta contextualizada baseada no catálogo
    """
    
    def __init__(self):
        super().__init__(name="product_catalog")
        self.register(self.get_product_info)
        self.register(self.get_sales_analysis)
    
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
    
    def get_sales_analysis(self, user_question: str) -> str:
        """
        Analisa dados de vendas históricas para responder perguntas sobre performance.
        
        Use esta ferramenta quando o usuário perguntar sobre:
        - Produtos mais vendidos (geral ou por período)
        - Performance de vendas
        - Histórico de saídas
        - Análises de receita
        
        Args:
            user_question: Pergunta sobre vendas históricas
                          Exemplos:
                          - "Qual produto mais vendeu?"
                          - "Top 5 produtos por receita"
                          - "Produtos que mais saíram na Black Friday"
        
        Returns:
            str: Análise detalhada das vendas com produtos ranqueados
        """
        try:
            print(f"📊 [Sales Analysis Tool] Analisando vendas: '{user_question}'")
            
            with Session(engine) as session:
                # Query SQL para produtos mais vendidos (all time)
                from sqlalchemy import func, desc
                
                query = (
                    select(
                        Produto.sku,
                        Produto.nome,
                        Produto.categoria,
                        Produto.estoque_atual,
                        func.sum(VendasHistoricas.quantidade).label('total_vendido'),
                        func.sum(VendasHistoricas.receita).label('receita_total')
                    )
                    .join(VendasHistoricas, Produto.id == VendasHistoricas.produto_id)
                    .group_by(Produto.id)
                    .order_by(desc('total_vendido'))
                    .limit(10)
                )
                
                results = session.exec(query).all()
                
                if not results:
                    return "Não encontrei dados de vendas no sistema."
                
                # Formata resposta
                response = "## 📈 Top Produtos por Volume de Vendas\n\n"
                
                for idx, row in enumerate(results, 1):
                    response += f"### {idx}. {row.nome}\n"
                    response += f"- **SKU**: {row.sku}\n"
                    response += f"- **Categoria**: {row.categoria}\n"
                    response += f"- **Total Vendido**: {row.total_vendido:,} unidades\n"
                    response += f"- **Receita Total**: R$ {row.receita_total:,.2f}\n"
                    response += f"- **Estoque Atual**: {row.estoque_atual} unidades\n"
                    response += "\n"
                
                print(f"✅ [Sales Analysis Tool] {len(results)} produtos analisados")
                return response
                
        except Exception as e:
            error_msg = f"Erro ao analisar vendas: {str(e)}"
            print(f"❌ [Sales Analysis Tool] Erro: {e}")
            import traceback
            traceback.print_exc()
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

    def compute_distance(self, lat1: float, lon1: float, lat2: float, lon2: float) -> str:
        """Calcula distância entre dois pontos geográficos (em km).

        Args:
            lat1, lon1: Coordenadas do ponto 1
            lat2, lon2: Coordenadas do ponto 2
        
        Returns:
            JSON com distância calculada
        """
        from math import radians, sin, cos, sqrt, atan2
        
        # Haversine formula
        R = 6371  # Raio da Terra em km
        
        lat1_rad, lon1_rad = radians(lat1), radians(lon1)
        lat2_rad, lon2_rad = radians(lat2), radians(lon2)
        
        dlat = lat2_rad - lat1_rad
        dlon = lon2_rad - lon1_rad
        
        a = sin(dlat/2)**2 + cos(lat1_rad) * cos(lat2_rad) * sin(dlon/2)**2
        c = 2 * atan2(sqrt(a), sqrt(1-a))
        distance = R * c
        
        return json.dumps({"distance_km": round(distance, 2)})


# ============================================================================
# FERRAMENTAS AVANÇADAS - Fase 2: Capacitação dos Agentes
# ============================================================================

def get_price_forecast_for_sku(sku: str, days_ahead: int = 7) -> str:
    """
    Use esta ferramenta para obter a previsão de preços futuros para um SKU específico.
    
    Args:
        sku: SKU do produto
        days_ahead: Número de dias à frente (padrão: 7)
    
    Returns:
        JSON com previsões de preço, datas e métricas do modelo
    """
    try:
        result = predict_prices_for_product(sku=sku, days_ahead=days_ahead)
        
        if "error" in result:
            return json.dumps({"error": result["error"]})
        
        # Calcular tendência
        prices = result.get("prices", [])
        if len(prices) >= 2:
            trend = "alta" if prices[-1] > prices[0] else "baixa"
            var_percent = ((prices[-1] - prices[0]) / prices[0]) * 100
        else:
            trend = "estável"
            var_percent = 0.0
        
        return json.dumps({
            "sku": sku,
            "previsoes": result.get("prices", []),
            "datas": result.get("dates", []),
            "tendencia": trend,
            "variacao_percentual": round(var_percent, 2),
            "modelo_usado": result.get("model_used", "desconhecido"),
            "metricas": result.get("metrics", {})
        }, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)


def search_market_trends_for_product(product_name: str) -> str:
    """
    Use esta ferramenta para pesquisar na web por notícias, artigos e análises 
    de mercado recentes que possam influenciar o preço de um produto.
    
    Args:
        product_name: Nome do produto ou categoria
    
    Returns:
        JSON com resultados da pesquisa de mercado
    """
    try:
        api_key = os.getenv("TAVILY_API_KEY")
        if not api_key:
            return json.dumps({
                "error": "Tavily API key não configurada",
                "info": "Configure a variável de ambiente TAVILY_API_KEY"
            }, ensure_ascii=False)
        
        if not TAVILY_AVAILABLE:
            return json.dumps({
                "error": "Tavily não disponível",
                "info": "Instale com: pip install tavily-python"
            }, ensure_ascii=False)
        
        # Construir query otimizada para pesquisa de tendências
        query = f"notícias e tendências de preço para {product_name} em 2025"
        
        client = TavilyClient(api_key=api_key)
        response = client.search(query, max_results=5, search_depth="advanced")
        
        insights = []
        for result in response.get("results", []):
            insights.append({
                "titulo": result.get("title"),
                "fonte": result.get("url"),
                "resumo": result.get("content", "")[:400],
                "score": result.get("score", 0.0)
            })
        
        return json.dumps({
            "produto": product_name,
            "total_resultados": len(insights),
            "insights": insights,
            "query_usada": query
        }, ensure_ascii=False)
        
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)


def find_supplier_offers_for_sku(sku: str) -> str:
    """
    Use esta ferramenta para encontrar todas as ofertas de fornecedores 
    para um produto específico, ordenadas por melhor preço.
    
    Args:
        sku: SKU do produto
    
    Returns:
        JSON com ofertas de fornecedores (preço, confiabilidade, prazo)
    """
    try:
        with Session(engine) as session:
            # Buscar produto
            produto = session.exec(select(Produto).where(Produto.sku == sku)).first()
            if not produto:
                return json.dumps({
                    "error": f"Produto com SKU '{sku}' não encontrado"
                }, ensure_ascii=False)
            
            # Buscar ofertas com join nos fornecedores
            from sqlmodel import select
            
            ofertas = session.exec(
                select(OfertaProduto, Fornecedor)
                .where(OfertaProduto.produto_id == produto.id)
                .join(Fornecedor, OfertaProduto.fornecedor_id == Fornecedor.id)
                .order_by(OfertaProduto.preco_ofertado)
            ).all()
            
            if not ofertas:
                return json.dumps({
                    "sku": sku,
                    "produto": produto.nome,
                    "ofertas": [],
                    "mensagem": "Nenhuma oferta encontrada para este produto"
                }, ensure_ascii=False)
            
            # Formatar ofertas
            ofertas_formatadas = []
            for oferta, fornecedor in ofertas:
                ofertas_formatadas.append({
                    "fornecedor": fornecedor.nome,
                    "preco": float(oferta.preco_ofertado),
                    "confiabilidade": fornecedor.confiabilidade,
                    "prazo_entrega_dias": fornecedor.prazo_entrega_dias,
                    "estoque_disponivel": oferta.estoque_disponivel,
                    "score_qualidade": round(fornecedor.confiabilidade * 100, 1),
                    "custo_por_dia": round(float(oferta.preco_ofertado) / fornecedor.prazo_entrega_dias, 2)
                })
            
            # Calcular melhor oferta (balance preço vs confiabilidade)
            if ofertas_formatadas:
                melhor_oferta = min(
                    ofertas_formatadas,
                    key=lambda x: x["preco"] * (2 - x["confiabilidade"])  # Penaliza baixa confiabilidade
                )
            else:
                melhor_oferta = None
            
            return json.dumps({
                "sku": sku,
                "produto": produto.nome,
                "total_ofertas": len(ofertas_formatadas),
                "ofertas": ofertas_formatadas,
                "melhor_oferta": melhor_oferta,
                "preco_medio": round(sum(o["preco"] for o in ofertas_formatadas) / len(ofertas_formatadas), 2) if ofertas_formatadas else 0
            }, ensure_ascii=False)
            
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)


def run_full_purchase_analysis(sku: str, reason: str = "reposição de estoque") -> str:
    """
    Use esta ferramenta para perguntas complexas que exigem uma recomendação 
    de compra completa, como 'Devo comprar o produto X?', 'Analise a necessidade 
    de reposição para o SKU Y', ou 'Faça uma recomendação de compra completa para Z'.
    
    Esta ferramenta delega a análise ao Time de Especialistas da Cadeia de Suprimentos.
    
    Args:
        sku: SKU do produto a analisar
        reason: Motivo da análise (padrão: "reposição de estoque")
    
    Returns:
        Análise completa com recomendação de compra formatada em markdown
    """
    try:
        print(f"🏢 [Delegação] Acionando Time de Especialistas para {sku}...")
        
        # Importação tardia para evitar import circular
        from app.agents.supply_chain_team import run_supply_chain_analysis
        
        query = f"Analise a necessidade de compra do produto {sku} para {reason}"
        result = run_supply_chain_analysis(query)
        
        print(f"✅ [Delegação] Time completou análise. Resultado: {result.get('decision', 'N/A')}")
        print(f"🔍 [Debug] Dados completos do resultado: {result}")
        
        # Extrai TODOS os dados disponíveis
        decision = result.get("decision", "manual_review")
        supplier = result.get("supplier", "N/A")
        price = result.get("price", 0)
        currency = result.get("currency", "BRL")
        quantity = result.get("quantity_recommended", 0)
        rationale = result.get("rationale", "Análise em andamento...")
        risk = result.get("risk_assessment", "")
        next_steps = result.get("next_steps", [])
        
        # Extrai dados dos sub-agentes (se disponível)
        need_restock = result.get("need_restock", None)
        forecast_notes = result.get("forecast_notes", "")
        market_prices = result.get("market_prices", [])
        logistics_analysis = result.get("logistics_analysis", {})
        selected_offer = logistics_analysis.get("selected_offer") if isinstance(logistics_analysis, dict) else None
        
        # Monta resposta formatada SEMPRE mostrando os dados disponíveis
        response = f"## 📊 Análise Completa de Compra - {sku}\n\n"
        
        # Cabeçalho com decisão
        if decision == "approve":
            response += "### ✅ RECOMENDAÇÃO: APROVAR COMPRA\n\n"
        elif decision == "reject":
            response += "### ❌ RECOMENDAÇÃO: NÃO COMPRAR\n\n"
        else:
            response += "### ⚠️ ANÁLISE COMPLETA (Requer Decisão Final)\n\n"
        
        # Dados do fornecedor (se disponível)
        if supplier and supplier != "N/A":
            response += f"**Fornecedor Recomendado:** {supplier}\n"
            if price > 0:
                response += f"**Preço Unitário:** {currency} {price:.2f}\n"
                if quantity > 0:
                    response += f"**Quantidade Sugerida:** {quantity} unidades\n"
                    response += f"**Valor Total:** {currency} {price * quantity:.2f}\n"
            response += "\n"
        elif selected_offer:
            response += f"**Melhor Oferta Encontrada:**\n"
            response += f"- Fornecedor: {selected_offer.get('source', 'N/A')}\n"
            response += f"- Preço: {currency} {selected_offer.get('price', 0):.2f}\n"
            if 'delivery_time_days' in selected_offer:
                response += f"- Prazo: {selected_offer.get('delivery_time_days')} dias\n"
            response += "\n"
        
        # Análise de necessidade
        if need_restock is not None:
            status = "✅ Necessita reposição" if need_restock else "⏸️ Estoque adequado"
            response += f"**Status de Estoque:** {status}\n\n"
        
        # Ofertas de mercado encontradas
        if market_prices and len(market_prices) > 0:
            response += f"**Ofertas Encontradas:** {len(market_prices)} fornecedores\n"
            for idx, offer in enumerate(market_prices[:3], 1):  # Top 3
                if isinstance(offer, dict):
                    response += f"{idx}. {offer.get('fornecedor', offer.get('source', 'N/A'))}: "
                    response += f"{currency} {offer.get('preco', offer.get('price', 0)):.2f}\n"
            response += "\n"
        
        # Justificativa (sempre mostrar)
        if rationale:
            response += f"**Análise e Justificativa:**\n{rationale}\n\n"
        
        if forecast_notes:
            response += f"**Notas de Previsão:**\n{forecast_notes}\n\n"
        
        # Avaliação de risco
        if risk:
            response += f"**Avaliação de Risco:**\n{risk}\n\n"
        
        # Próximos passos
        if next_steps and len(next_steps) > 0:
            response += "**Próximos Passos:**\n"
            for step in next_steps:
                response += f"- {step}\n"
        else:
            # Adiciona passos padrão se não houver
            response += "**Próximos Passos:**\n"
            response += "- Revisar análise detalhada acima\n"
            response += "- Validar disponibilidade de orçamento\n"
            response += "- Contatar fornecedor selecionado\n"
        
        return response
        
    except Exception as e:
        error_msg = f"❌ Erro ao executar análise do time: {str(e)}"
        print(error_msg)
        import traceback
        traceback.print_exc()
        return error_msg


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
