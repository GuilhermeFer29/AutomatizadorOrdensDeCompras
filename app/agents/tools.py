"""
Definição das ferramentas LangChain para orquestrar os serviços existentes.

Este arquivo encapsula as funções dos serviços existentes como Tools do LangChain,
permitindo que os agentes de IA as utilizem de forma inteligente.
"""

import json
import os
from typing import Tuple, Dict, Any
from langchain.tools import tool
from sqlmodel import Session, select
from app.core.database import engine
from app.models.models import Produto, PrecosHistoricos, OrdemDeCompra
from app.services.scraping_service import scrape_and_save_price
from app.services.ml_service import get_forecast
from decimal import Decimal

# Importações opcionais
try:
    from tavily import TavilyClient
    TAVILY_AVAILABLE = True
except ImportError:
    TAVILY_AVAILABLE = False

# Constantes
DEFAULT_FORECAST_HORIZON = 14


@tool
def get_product_info(product_sku: str) -> str:
    """
    Busca informações básicas de um produto no banco de dados, incluindo estoque atual e mínimo.

    Args:
        product_sku (str): O SKU do produto a ser consultado.

    Returns:
        str: Informações do produto em formato JSON, incluindo estoque_atual, estoque_minimo, nome, etc.
    """
    with Session(engine) as session:
        produto = session.exec(select(Produto).where(Produto.sku == product_sku)).first()
        if not produto:
            return f"Produto com SKU {product_sku} não encontrado."

        info = {
            "sku": produto.sku,
            "nome": produto.nome,
            "estoque_atual": produto.estoque_atual,
            "estoque_minimo": produto.estoque_minimo,
            "categoria": produto.categoria,
            "preco_atual": produto.preco_atual
        }
        return json.dumps(info, ensure_ascii=False)


@tool
def search_market_price(product_sku: str) -> str:
    """
    Busca o preço atual do produto no mercado usando scraping.

    Args:
        product_sku (str): O SKU do produto para buscar o preço.

    Returns:
        str: Preço encontrado ou mensagem de erro.
    """
    try:
        # Primeiro, obter o nome do produto
        with Session(engine) as session:
            produto = session.exec(select(Produto).where(Produto.sku == product_sku)).first()
            if not produto:
                return f"Produto com SKU {product_sku} não encontrado."

        # Executar scraping
        preco = scrape_and_save_price(produto.id)
        if preco:
            return f"Preço encontrado: R$ {preco:.2f}"
        else:
            return "Não foi possível encontrar o preço no mercado."
    except Exception as e:
        return f"Erro ao buscar preço: {str(e)}"


@tool
def get_forecast_tool(product_sku: str) -> str:
    """
    Obtém a previsão de demanda para um produto específico.

    Args:
        product_sku (str): O SKU do produto para o qual a previsão será gerada.

    Returns:
        str: Previsão de demanda em formato JSON ou mensagem de erro.
    """
    try:
        forecast = get_forecast(product_sku)
        return json.dumps({"sku": product_sku, "forecast": forecast}, ensure_ascii=False)
    except Exception as e:
        return f"Erro ao obter previsão: {str(e)}"


# Lista de ferramentas disponíveis para os agentes
TOOLS = [
    get_product_info,
    search_market_price,
    get_forecast_tool
]


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


class SupplyChainToolkit:
    """Toolkit com ferramentas para análise de cadeia de suprimentos."""
    
    def __init__(self):
        self.name = "supply_chain_toolkit"
        self.tools = [
            self.lookup_product,
            self.load_demand_forecast,
            self.find_supplier_offers,
            self.compute_distance,
        ]
        
        # Adiciona Tavily (recomendado para buscas contextuais)
        if TAVILY_AVAILABLE and os.getenv("TAVILY_API_KEY"):
            self.tools.append(self.tavily_search)
    
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
        """
        ⚡ OTIMIZADO COM CACHE: Previsões ML armazenadas para consultas repetidas.
        
        📊 IMPORTANTE: Esta ferramenta retorna previsões de PREÇO (não quantidade).
        Use a tendência de preço como proxy para decisões de compra:
        - Preço subindo → Comprar agora pode ser vantajoso
        - Preço caindo → Esperar pode economizar
        - Preço estável → Decisão baseada em outros fatores
        
        Para previsão de QUANTIDADE vendida, combine com get_sales_analysis.

        Args:
            sku: O SKU único do produto.
            horizon_days: Quantidade de dias futuros (padrão: 14).
        
        Returns:
            JSON com previsões ML de preço futuro e métricas do modelo.
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
    
    def find_supplier_offers(self, sku: str) -> str:
        """
        Busca todas as ofertas de fornecedores para um produto específico.
        
        Args:
            sku: SKU do produto
        
        Returns:
            JSON com lista de ofertas (fornecedor, preço, confiabilidade, prazo)
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
                        "mensagem": "Nenhuma oferta encontrada"
                    }, ensure_ascii=False)
                
                # Formatar ofertas
                ofertas_formatadas = []
                for oferta, fornecedor in ofertas:
                    ofertas_formatadas.append({
                        "fornecedor": fornecedor.nome,
                        "preco": float(oferta.preco_ofertado),
                        "confiabilidade": fornecedor.confiabilidade,
                        "prazo_entrega_dias": fornecedor.prazo_entrega_dias,
                        "estoque_disponivel": oferta.estoque_disponivel
                    })
                
                return json.dumps({
                    "sku": sku,
                    "produto": produto.nome,
                    "total_ofertas": len(ofertas_formatadas),
                    "ofertas": ofertas_formatadas,
                    "preco_medio": round(sum(o["preco"] for o in ofertas_formatadas) / len(ofertas_formatadas), 2)
                }, ensure_ascii=False)
                
        except Exception as e:
            return json.dumps({"error": str(e)}, ensure_ascii=False)

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

@tool
def get_price_forecast_for_sku(sku: str, days_ahead: int = 7) -> str:
    """Obtém previsões ML de preços futuros para um produto específico usando LightGBM.
    
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


@tool
def find_supplier_offers_for_sku(sku: str) -> str:
    """Busca ofertas de fornecedores para um produto, ordenadas por melhor preço.
    
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


@tool
def run_full_purchase_analysis(sku: str, reason: str = "reposição de estoque") -> str:
    """Delega análise completa de compra ao Time de Especialistas.
    
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


@tool
def create_purchase_order_tool(sku: str, quantity: int, price_per_unit: float, supplier: str = "Agente de IA") -> str:
    """Cria uma ordem de compra pendente para aprovação humana.
    
    Esta ferramenta permite que o agente de IA crie ordens de compra que serão
    revisadas e aprovadas por um humano antes de serem confirmadas.
    
    Args:
        sku: SKU do produto
        quantity: Quantidade a comprar (deve ser > 0)
        price_per_unit: Preço unitário do produto
        supplier: Nome do fornecedor (padrão: "Agente de IA")
    
    Returns:
        JSON com status da criação da ordem
    """
    try:
        if quantity <= 0:
            return json.dumps({
                "error": "A quantidade deve ser maior que zero",
                "status": "failed"
            }, ensure_ascii=False)
        
        if price_per_unit <= 0:
            return json.dumps({
                "error": "O preço deve ser maior que zero",
                "status": "failed"
            }, ensure_ascii=False)
        
        with Session(engine) as session:
            # Buscar o produto pelo SKU
            produto = session.exec(select(Produto).where(Produto.sku == sku)).first()
            if not produto:
                return json.dumps({
                    "error": f"Produto com SKU '{sku}' não encontrado",
                    "status": "failed"
                }, ensure_ascii=False)
            
            # Calcular valor total
            valor_total = Decimal(str(price_per_unit * quantity))
            
            # Criar nova ordem com status 'pending'
            new_order = OrdemDeCompra(
                produto_id=produto.id,
                quantidade=quantity,
                valor=valor_total,
                status="pending",
                origem=supplier
            )
            
            session.add(new_order)
            session.commit()
            session.refresh(new_order)
            
            return json.dumps({
                "status": "success",
                "order_id": new_order.id,
                "sku": sku,
                "produto": produto.nome,
                "quantidade": quantity,
                "preco_unitario": price_per_unit,
                "valor_total": float(valor_total),
                "status_ordem": "pending",
                "origem": supplier,
                "mensagem": f"Ordem #{new_order.id} criada com sucesso e aguardando aprovação"
            }, ensure_ascii=False)
    
    except Exception as e:
        return json.dumps({
            "error": f"Erro ao criar ordem de compra: {str(e)}",
            "status": "failed"
        }, ensure_ascii=False)


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
