"""
Ferramentas (Tools) do Agente - Refatoradas para Agno (Pure Python).

Este arquivo define as funções que o agente pode chamar.
No Agno, qualquer função Python com docstrings e type hints é uma ferramenta válida.
NÃO HÁ dependência de LangChain aqui.
"""

import os
import json
from decimal import Decimal
from typing import Dict, Any, List, Tuple
from sqlmodel import Session, select
from app.core.database import engine
from app.models.models import Produto, OfertaProduto, Fornecedor, OrdemDeCompra
from app.services.scraping_service import scrape_and_save_price
from app.services.ml_service import get_forecast

# Importações opcionais
try:
    from tavily import TavilyClient
    TAVILY_AVAILABLE = True
except ImportError:
    TAVILY_AVAILABLE = False

# Constantes
DEFAULT_FORECAST_HORIZON = 14

# ============================================================================
# FERRAMENTAS PRINCIPAIS (Product Tools)
# ============================================================================

def get_product_info(product_sku: str) -> str:
    """
    Busca informações detalhadas de um produto no banco de dados.

    Use esta ferramenta quando precisar saber estoque, preço, categoria ou status
    de um produto específico identificado pelo SKU.

    Args:
        product_sku (str): O SKU do produto (ex: 'SKU_001').

    Returns:
        str: JSON com sku, nome, estoque_atual, estoque_minimo, etc.
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
            "preco_atual": float(produto.precos[0].preco) if produto.precos else 0.0,
            "status_reposicao": "ALERTA" if produto.estoque_atual <= produto.estoque_minimo else "OK"
        }
        return json.dumps(info, ensure_ascii=False)


def search_market_price(product_sku: str) -> str:
    """
    Realiza busca em tempo real (scraping) do preço de mercado de um produto.

    Esta operação pode ser lenta. Use apenas se precisar de dados externos atualizados.

    Args:
        product_sku (str): O SKU do produto.

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
            return f"Preço de mercado encontrado via scraping: R$ {preco:.2f}"
        else:
            return "Não foi possível encontrar o preço no mercado externo no momento."
    except Exception as e:
        return f"Erro ao buscar preço de mercado: {str(e)}"


def get_forecast_tool(product_sku: str) -> str:
    """
    Obtém a previsão de demanda futura (quantidade) para um produto.

    Args:
        product_sku (str): SKU do produto.

    Returns:
        str: JSON com a previsão de demanda calculada pelo modelo.
    """
    try:
        forecast = get_forecast(product_sku)
        return json.dumps({"sku": product_sku, "demand_forecast": forecast}, ensure_ascii=False)
    except Exception as e:
        return f"Erro ao obter previsão: {str(e)}"


def get_price_forecast_for_sku(sku: str, days_ahead: int = 7) -> str:
    """
    Obtém previsões de PREÇO futuro usando modelo de Machine Learning (LightGBM).
    
    Use para analisar tendências de preço (alta/baixa) para decidir o momento da compra.
    
    Args:
        sku: SKU do produto
        days_ahead: Número de dias à frente (padrão: 7)
    
    Returns:
        str: JSON com previsões de preço, datas e métricas do modelo
    """
    # Importação tardia para evitar círculo, se necessario, ou assumeml_service importado
    try:
        from app.services.ml_service import predict_prices_for_product
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


# ============================================================================
# SUPPLY CHAIN TOOLKIT - Funções de Apoio
# ============================================================================

def find_supplier_offers_for_sku(sku: str) -> str:
    """
    Busca ofertas de fornecedores cadastradas para um produto.
    
    Use para comparar preços e prazos entre fornecedores conhecidos.
    
    Args:
        sku: SKU do produto
    
    Returns:
        str: JSON com lista de ofertas e recomendação B2B.
    """
    try:
        with Session(engine) as session:
            # Buscar produto
            produto = session.exec(select(Produto).where(Produto.sku == sku)).first()
            if not produto:
                return json.dumps({"error": f"Produto com SKU '{sku}' não encontrado"}, ensure_ascii=False)
            
            # Buscar ofertas
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
            
            # Formatar e Rankear
            ofertas_formatadas = []
            for oferta, fornecedor in ofertas:
                ofertas_formatadas.append({
                    "fornecedor": fornecedor.nome,
                    "preco": float(oferta.preco_ofertado),
                    "confiabilidade": fornecedor.confiabilidade,
                    "prazo_entrega_dias": fornecedor.prazo_entrega_dias,
                    "estoque_disponivel": oferta.estoque_disponivel,
                    "custo_por_dia": round(float(oferta.preco_ofertado) / fornecedor.prazo_entrega_dias, 2)
                })
            
            # Algoritmo de seleção simples (pode ser expandido)
            melhor_oferta = min(ofertas_formatadas, key=lambda x: x["preco"])
            
            return json.dumps({
                "sku": sku,
                "produto": produto.nome,
                "total_ofertas": len(ofertas_formatadas),
                "ofertas": ofertas_formatadas,
                "melhor_oferta": melhor_oferta,
                "criterio_selecao": "menor_preco"
            }, ensure_ascii=False)
            
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)


def run_full_purchase_analysis(sku: str, reason: str = "reposição de estoque") -> str:
    """
    Delega análise complexa de compra ao algoritmo de Supply Chain.
    
    Retorna uma recomendação formatada (Aprovar/Rejeitar) baseada em múltiplos fatores.
    
    Args:
        sku: SKU do produto
        reason: Motivo da análise
    
    Returns:
        str: Texto formatado em Markdown com a recomendação.
    """
    # Para evitar complexidade excessiva neste refactor, vamos implementar uma versão simplificada
    # que chama as outras ferramentas e agrega a lógica, ou mantemos a delegação se o team existir.
    # Assumindo que queremos manter a lógica original:
    
    try:
        # Importação tardia do agente especialista (se ainda existir) ou recriar lógica aqui
        # Como estamos migrando para Agno Puro, é melhor que esta ferramenta seja autônoma ou chame outras.
        # Vamos manter a implementação como um agregador de dados por enquanto.
        
        info = json.loads(get_product_info(sku))
        if "error" in info: return info["error"]
        
        forecast = json.loads(get_forecast_tool(sku))
        offers = json.loads(find_supplier_offers_for_sku(sku))
        price_forecast = json.loads(get_price_forecast_for_sku(sku))
        
        # Validação simples
        need_restock = info.get("status_reposicao") == "ALERTA"
        has_offers = len(offers.get("ofertas", [])) > 0
        price_trend = price_forecast.get("tendencia", "estável")
        
        decision = "MANUAL REVIEW"
        rationale = ""
        
        if need_restock:
            if has_offers:
                if price_trend == "baixa":
                    decision = "WAIT"
                    rationale = "Estoque baixo, mas preço caindo. Tente postergar ou compra mínima."
                else:
                    decision = "APPROVE"
                    rationale = "Estoque crítico e ofertas disponíveis. Comprar imediatamente."
            else:
                decision = "ALERT"
                rationale = "Estoque crítico e SEM fornecedores. Ação urgente necessária."
        else:
            decision = "REJECT"
            rationale = "Estoque adequado. Compra desnecessária."
            
        return f"""## Análise Automática de Compra ({sku})
**Decisão:** {decision}

**Motivo:** {rationale}

**Dados Analisados:**
- Estoque: {info.get('estoque_atual')} (Min: {info.get('estoque_minimo')})
- Tendência Preço: {price_trend}
- Ofertas Disponíveis: {len(offers.get('ofertas', []))}
"""
    except Exception as e:
        return f"Erro na análise: {str(e)}"


def list_all_products(category: str = None, only_low_stock: bool = False) -> str:
    """
    Lista todos os produtos do catálogo com informações de estoque e status.
    
    Use esta ferramenta quando o usuário perguntar sobre:
    - "Como está meu estoque?" (sem SKU específico)
    - "Quais produtos precisam de reposição?"
    - "Liste todos os produtos"
    - "Resumo geral do inventário"
    
    Args:
        category: Filtrar por categoria (opcional). Ex: 'Eletrônicos', 'Ferramentas'
        only_low_stock: Se True, retorna apenas produtos com estoque baixo/crítico
    
    Returns:
        str: JSON com lista de produtos, totais e alertas
    """
    try:
        with Session(engine) as session:
            query = select(Produto)
            if category:
                query = query.where(Produto.categoria == category)
            
            produtos = session.exec(query).all()
            
            if not produtos:
                return json.dumps({
                    "total_produtos": 0,
                    "mensagem": "Nenhum produto encontrado no catálogo."
                }, ensure_ascii=False)
            
            produtos_list = []
            alertas = []
            total_valor_estoque = 0.0
            
            for p in produtos:
                status = "OK"
                if p.estoque_atual <= 0:
                    status = "SEM_ESTOQUE"
                elif p.estoque_atual <= p.estoque_minimo:
                    status = "ALERTA_BAIXO"
                elif p.estoque_atual <= p.estoque_minimo * 1.5:
                    status = "ATENÇÃO"
                
                # Filtra se only_low_stock
                if only_low_stock and status == "OK":
                    continue
                
                preco_atual = float(p.precos[0].preco) if p.precos else 0.0
                valor_estoque = preco_atual * p.estoque_atual
                total_valor_estoque += valor_estoque
                
                produto_info = {
                    "sku": p.sku,
                    "nome": p.nome,
                    "categoria": p.categoria or "Sem categoria",
                    "estoque_atual": p.estoque_atual,
                    "estoque_minimo": p.estoque_minimo,
                    "preco_unitario": preco_atual,
                    "valor_em_estoque": round(valor_estoque, 2),
                    "status": status
                }
                produtos_list.append(produto_info)
                
                if status in ["SEM_ESTOQUE", "ALERTA_BAIXO"]:
                    alertas.append({
                        "sku": p.sku,
                        "nome": p.nome,
                        "status": status,
                        "estoque_atual": p.estoque_atual,
                        "estoque_minimo": p.estoque_minimo
                    })
            
            # Resumo
            total_ok = len([p for p in produtos_list if p["status"] == "OK"])
            total_alerta = len([p for p in produtos_list if p["status"] in ["ALERTA_BAIXO", "ATENÇÃO"]])
            total_critico = len([p for p in produtos_list if p["status"] == "SEM_ESTOQUE"])
            
            return json.dumps({
                "total_produtos": len(produtos_list),
                "resumo": {
                    "estoque_ok": total_ok,
                    "estoque_alerta": total_alerta,
                    "estoque_critico": total_critico,
                    "valor_total_estoque": round(total_valor_estoque, 2)
                },
                "alertas_prioritarios": alertas[:5],  # Top 5 alertas
                "produtos": produtos_list
            }, ensure_ascii=False)
            
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)


def create_purchase_order_tool(sku: str, quantity: int, price_per_unit: float, supplier: str = "Agente de IA") -> str:
    """
    Cria uma ordem de compra no sistema.

    Args:
        sku: SKU do produto
        quantity: Quantidade a comprar
        price_per_unit: Preço unitário acordado
        supplier: Nome do fornecedor

    Returns:
        str: JSON com resultado da operação (sucesso/falha e ID da ordem).
    """
    try:
        if quantity <= 0 or price_per_unit <= 0:
            return json.dumps({"error": "Quantidade e preço devem ser positivos"}, ensure_ascii=False)
        
        with Session(engine) as session:
            produto = session.exec(select(Produto).where(Produto.sku == sku)).first()
            if not produto:
                return json.dumps({"error": f"Produto {sku} não encontrado"}, ensure_ascii=False)
            
            valor_total = Decimal(str(price_per_unit * quantity))
            
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
                "mensagem": f"Ordem #{new_order.id} criada com sucesso."
            }, ensure_ascii=False)
            
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)
