"""
Serviço Híbrido: RAG + SQL para responder QUALQUER pergunta sobre produtos.

ESTRATÉGIA:
1. LLM analisa a pergunta e decide qual ferramenta usar
2. Perguntas estruturadas (filtros, agregações) → SQL Tool
3. Perguntas semânticas (descrições, comparações) → RAG
4. Perguntas complexas → Combina ambos
"""

from typing import Dict, Any
from sqlmodel import Session
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
import json


def analyze_query_intent(user_question: str) -> Dict[str, Any]:
    """
    Usa LLM para analisar a intenção da pergunta e decidir qual ferramenta usar.
    
    Returns:
        {
            "query_type": "sql" | "rag" | "hybrid",
            "needs_filter": bool,
            "filters": {...},
            "semantic_query": str
        }
    """
    llm = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        temperature=0.1
    )
    
    prompt = ChatPromptTemplate.from_template("""Você é um analisador de consultas de banco de dados.

Analise a pergunta do usuário e determine:
1. Se precisa de consulta SQL estruturada (filtros, agregações, comparações numéricas)
2. Se precisa de busca semântica RAG (descrições, características, informações textuais)
3. Se precisa de previsões ML (preços futuros, tendências, projeções)
4. Se precisa de análise de vendas históricas (mais vendido, períodos específicos)
5. Ou se precisa combinar múltiplas ferramentas (híbrido)

PERGUNTA: {question}

Retorne um JSON com:
{{
    "query_type": "sql" | "rag" | "hybrid" | "ml_prediction" | "sales_analysis",
    "needs_stock_filter": true/false,
    "stock_filter_type": "low" | "high" | "all" | null,
    "needs_category_filter": true/false,
    "category": "categoria" | null,
    "needs_sorting": true/false,
    "sort_by": "stock_asc" | "stock_desc" | "sales_desc" | null,
    "needs_prediction": true/false,
    "prediction_type": "price" | "demand" | null,
    "time_filter": {{"month": "maio" | null, "year": 2025 | null}},
    "semantic_aspect": "descrição do que buscar semanticamente" | null,
    "reasoning": "breve explicação da decisão"
}}

Responda APENAS com o JSON, sem texto adicional.""")
    
    try:
        response = llm.invoke(prompt.format(question=user_question))
        # Remove markdown code blocks se existirem
        content = response.content.strip()
        if content.startswith("```json"):
            content = content[7:]
        if content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]
        
        return json.loads(content.strip())
    except Exception as e:
        print(f"⚠️ Erro ao analisar intent: {e}")
        # Fallback: usa RAG por padrão
        return {
            "query_type": "rag",
            "needs_stock_filter": False,
            "reasoning": "Fallback para RAG devido a erro na análise"
        }


def execute_hybrid_query(user_question: str, db_session: Session) -> str:
    """
    Executa consulta híbrida combinando SQL e RAG conforme necessário.
    
    Args:
        user_question: Pergunta do usuário
        db_session: Sessão do banco de dados
        
    Returns:
        Resposta formatada em linguagem natural
    """
    # 1. Analisa a intenção da pergunta
    intent = analyze_query_intent(user_question)
    print(f"🧠 Intent detectado: {intent.get('query_type')} - {intent.get('reasoning')}")
    
    query_type = intent.get("query_type", "rag")
    
    # 2. Executa análise de vendas históricas se necessário
    sales_data = None
    if query_type in ["sales_analysis", "hybrid"] or intent.get("time_filter", {}).get("month"):
        sales_data = execute_sales_analysis(intent, db_session)
        print(f"📈 Análise de vendas retornou {len(sales_data) if isinstance(sales_data, list) else 'dados'}")
    
    # 3. Executa consulta SQL se necessário
    sql_results = None
    if query_type in ["sql", "hybrid"]:
        sql_results = execute_sql_query(intent, db_session)
        print(f"📊 SQL retornou {len(sql_results) if isinstance(sql_results, list) else 'dados'}")
    
    # 4. Executa previsões ML se necessário
    ml_predictions = None
    if query_type in ["ml_prediction", "hybrid"] or intent.get("needs_prediction"):
        ml_predictions = execute_ml_predictions(intent, db_session, sales_data)
        print(f"🎯 ML Predictions retornou dados para {len(ml_predictions) if isinstance(ml_predictions, list) else 0} produtos")
    
    # 5. Executa RAG se necessário
    rag_response = None
    if query_type in ["rag", "hybrid"]:
        from app.services.rag_service import query_product_catalog_with_google_rag
        
        # Enriquece contexto com todos os dados disponíveis
        context_data = {}
        if sql_results:
            context_data["produtos"] = sql_results
        if sales_data:
            context_data["vendas"] = sales_data
        if ml_predictions:
            context_data["previsoes"] = ml_predictions
        
        if context_data:
            enhanced_query = f"{user_question}\n\nDados disponíveis: {json.dumps(context_data, ensure_ascii=False)}"
            rag_response = query_product_catalog_with_google_rag(enhanced_query)
        else:
            rag_response = query_product_catalog_with_google_rag(user_question)
        
        print(f"🤖 RAG respondeu: {rag_response[:100]}...")
    
    # 6. Combina resultados e gera resposta final
    return format_final_response(
        user_question, 
        sql_results, 
        rag_response, 
        intent,
        sales_data=sales_data,
        ml_predictions=ml_predictions
    )


def execute_sql_query(intent: Dict[str, Any], db_session: Session) -> Any:
    """
    Executa consulta SQL baseada no intent analisado.
    """
    from app.services.sql_query_tool import (
        query_products_with_filters,
        get_stock_statistics,
        get_products_sorted_by_stock
    )
    
    # Consulta produtos com estoque baixo
    if intent.get("needs_stock_filter") and intent.get("stock_filter_type") == "low":
        return query_products_with_filters(
            db_session,
            estoque_baixo=True,
            categoria=intent.get("category"),
            limit=50
        )
    
    # Consulta produtos ordenados por estoque
    if intent.get("needs_sorting"):
        order = "asc" if intent.get("sort_by") == "stock_asc" else "desc"
        return get_products_sorted_by_stock(db_session, order=order, limit=20)
    
    # Estatísticas gerais
    if "estatística" in intent.get("reasoning", "").lower() or "quantos" in intent.get("reasoning", "").lower():
        return get_stock_statistics(db_session)
    
    # Fallback: retorna produtos com filtros gerais
    return query_products_with_filters(
        db_session,
        estoque_baixo=intent.get("stock_filter_type") == "low",
        categoria=intent.get("category"),
        limit=50
    )


def execute_sales_analysis(intent: Dict[str, Any], db_session: Session) -> Any:
    """
    Executa análise de vendas históricas baseada no intent.
    """
    from sqlmodel import select, func
    from app.models.models import VendasHistoricas, Produto
    from datetime import datetime
    
    time_filter = intent.get("time_filter", {})
    month = time_filter.get("month")
    
    # Mapear nome do mês para número
    month_map = {
        "janeiro": 1, "fevereiro": 2, "março": 3, "abril": 4,
        "maio": 5, "junho": 6, "julho": 7, "agosto": 8,
        "setembro": 9, "outubro": 10, "novembro": 11, "dezembro": 12
    }
    
    month_num = month_map.get(month.lower()) if month else None
    
    try:
        # Query: produtos mais vendidos no mês específico
        query = (
            select(
                Produto.sku,
                Produto.nome,
                func.sum(VendasHistoricas.quantidade).label("total_vendido"),
                func.sum(VendasHistoricas.receita).label("receita_total"),
                func.count(VendasHistoricas.id).label("num_transacoes")
            )
            .join(VendasHistoricas, Produto.id == VendasHistoricas.produto_id)
        )
        
        # Filtrar por mês se especificado
        if month_num:
            query = query.where(func.month(VendasHistoricas.data) == month_num)
        
        # Agrupar e ordenar
        query = (
            query
            .group_by(Produto.sku, Produto.nome)
            .order_by(func.sum(VendasHistoricas.quantidade).desc())
            .limit(20)
        )
        
        results = db_session.exec(query).all()
        
        return [
            {
                "sku": r.sku,
                "nome": r.nome,
                "total_vendido": int(r.total_vendido),
                "receita_total": float(r.receita_total),
                "num_transacoes": int(r.num_transacoes),
                "ticket_medio": float(r.receita_total / r.total_vendido) if r.total_vendido > 0 else 0
            }
            for r in results
        ]
    except Exception as e:
        print(f"❌ Erro na análise de vendas: {e}")
        return []


def execute_ml_predictions(intent: Dict[str, Any], db_session: Session, sales_data: Any = None) -> Any:
    """
    Executa previsões ML para produtos relevantes.
    """
    from app.ml.prediction import predict_prices
    
    try:
        # Se tem dados de vendas, pega top produtos
        if sales_data and len(sales_data) > 0:
            top_skus = [item["sku"] for item in sales_data[:5]]  # Top 5
        else:
            # Pega produtos aleatórios
            from app.models.models import Produto
            from sqlmodel import select
            results = db_session.exec(select(Produto.sku).limit(5)).all()
            top_skus = results
        
        predictions = []
        for sku in top_skus:
            try:
                pred = predict_prices(sku, days_ahead=14)
                if pred:
                    predictions.append({
                        "sku": sku,
                        "previsoes": pred.get("prices", [])[:7],  # Próximos 7 dias
                        "datas": pred.get("dates", [])[:7],
                        "metricas": pred.get("metrics", {}),
                        "tendencia": "alta" if len(pred.get("prices", [])) > 1 and pred["prices"][-1] > pred["prices"][0] else "baixa"
                    })
            except Exception as e:
                print(f"⚠️ Erro ao prever {sku}: {e}")
                continue
        
        return predictions if predictions else None
    except Exception as e:
        print(f"❌ Erro nas previsões ML: {e}")
        return None


def format_final_response(
    question: str,
    sql_results: Any,
    rag_response: str,
    intent: Dict[str, Any],
    sales_data: Any = None,
    ml_predictions: Any = None
) -> str:
    """
    Formata resposta final combinando SQL, RAG, Vendas e ML Predictions.
    """
    # Se tem dados de vendas + previsões, usa LLM avançado
    if sales_data or ml_predictions:
        return combine_advanced_response(question, sql_results, rag_response, sales_data, ml_predictions)
    
    # Se só tem RAG, retorna direto
    if sql_results is None and rag_response:
        return rag_response
    
    # Se só tem SQL, formata os dados
    if sql_results and not rag_response:
        return format_sql_results(sql_results, question)
    
    # Se tem ambos, usa LLM para combinar
    if sql_results and rag_response:
        return combine_with_llm(question, sql_results, rag_response)
    
    return "Desculpe, não consegui encontrar informações relevantes para sua pergunta."


def format_sql_results(results: Any, question: str) -> str:
    """
    Formata resultados SQL em linguagem natural.
    Limita a 10 produtos para evitar respostas muito longas.
    """
    # Se é estatística
    if isinstance(results, dict) and "total_produtos" in results:
        return (
            f"📊 **Estatísticas do Estoque:**\n\n"
            f"• Total de produtos: {results['total_produtos']}\n"
            f"• Produtos com estoque baixo: {results['produtos_estoque_baixo']}\n"
            f"• Estoque total: {results['estoque_total_unidades']} unidades\n"
        )
    
    # Se é lista de produtos
    if isinstance(results, list):
        if not results:
            return "Não encontrei produtos que atendam aos critérios da sua busca."
        
        # Produtos com estoque baixo
        estoque_baixo = [p for p in results if p.get("estoque_baixo")]
        if estoque_baixo:
            total = len(estoque_baixo)
            limite = 10  # Limita a 10 produtos para não exceder tamanho da coluna
            
            response = f"⚠️ **Encontrei {total} produto(s) com estoque baixo:**\n\n"
            
            for p in estoque_baixo[:limite]:
                diferenca = p.get("diferenca", 0)
                response += (
                    f"• **{p['nome']}** (SKU: {p['sku']})\n"
                    f"  - Estoque: {p['estoque_atual']}/{p['estoque_minimo']} unidades\n"
                    f"  - Faltam: {abs(diferenca)} unidades\n\n"
                )
            
            if total > limite:
                response += f"\n_...e mais {total - limite} produto(s). Use filtros para refinar a busca._"
            
            return response
        
        # Produtos gerais
        total = len(results)
        limite = 10
        
        response = f"📦 **Encontrei {total} produto(s):**\n\n"
        for p in results[:limite]:
            response += (
                f"• **{p['nome']}** (SKU: {p['sku']})\n"
                f"  - Estoque: {p['estoque_atual']} unidades\n\n"
            )
        
        if total > limite:
            response += f"\n_...e mais {total - limite} produto(s)._"
        
        return response
    
    return str(results)


def combine_advanced_response(
    question: str,
    sql_data: Any,
    rag_response: str,
    sales_data: Any,
    ml_predictions: Any
) -> str:
    """
    Combina TODOS os dados (SQL + RAG + Vendas + ML) em resposta natural.
    """
    llm = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        temperature=0.4  # Um pouco mais criativo para respostas naturais
    )
    
    prompt = ChatPromptTemplate.from_template("""Você é um assistente inteligente especializado em gestão de compras industriais.

Responda à pergunta do usuário de forma NATURAL, CONVERSACIONAL e COMPLETA, combinando todas as fontes de informação disponíveis.

PERGUNTA: {question}

📊 DADOS DE VENDAS HISTÓRICAS:
{sales_data}

🎯 PREVISÕES DE MACHINE LEARNING:
{ml_predictions}

📦 DADOS DE PRODUTOS (SQL):
{sql_data}

📚 CONTEXTO ADICIONAL (RAG):
{rag_context}

INSTRUÇÕES IMPORTANTES:
1. Responda de forma natural e conversacional, como se estivesse falando com um colega
2. Use os dados de vendas para identificar produtos mais populares
3. Use as previsões ML para dar insights sobre tendências futuras
4. Combine tudo em uma narrativa coerente
5. Use emojis e formatação markdown para tornar a resposta mais agradável
6. Se houver tendências de preço, mencione explicitamente
7. Seja específico com números, datas e valores
8. Finalize com uma recomendação ou insight útil

Resposta:""")
    
    try:
        response = llm.invoke(prompt.format(
            question=question,
            sales_data=json.dumps(sales_data, ensure_ascii=False, indent=2) if sales_data else "Não disponível",
            ml_predictions=json.dumps(ml_predictions, ensure_ascii=False, indent=2) if ml_predictions else "Não disponível",
            sql_data=json.dumps(sql_data, ensure_ascii=False, indent=2) if sql_data else "Não disponível",
            rag_context=rag_response if rag_response else "Não disponível"
        ))
        return response.content
    except Exception as e:
        print(f"❌ Erro ao gerar resposta avançada: {e}")
        # Fallback: formata vendas se disponível
        if sales_data:
            return format_sales_results(sales_data, question)
        return "Desculpe, ocorreu um erro ao processar sua pergunta."


def format_sales_results(sales_data: list, question: str) -> str:
    """Formata resultados de vendas de forma visual."""
    if not sales_data:
        return "Não encontrei dados de vendas para esse período."
    
    response = "📈 **Análise de Vendas:**\n\n"
    
    for i, item in enumerate(sales_data[:10], 1):
        response += (
            f"{i}. **{item['nome']}** (SKU: {item['sku']})\n"
            f"   • Total vendido: {item['total_vendido']} unidades\n"
            f"   • Receita: R$ {item['receita_total']:.2f}\n"
            f"   • Ticket médio: R$ {item['ticket_medio']:.2f}\n\n"
        )
    
    if len(sales_data) > 10:
        response += f"\n_...e mais {len(sales_data) - 10} produtos._"
    
    return response


def combine_with_llm(question: str, sql_data: Any, rag_response: str) -> str:
    """
    Usa LLM para combinar dados SQL e resposta RAG em uma resposta coerente.
    """
    llm = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        temperature=0.3
    )
    
    prompt = ChatPromptTemplate.from_template("""Você é um assistente especializado em produtos industriais.

Combine as informações estruturadas do banco de dados com o contexto semântico para responder a pergunta do usuário.

PERGUNTA: {question}

DADOS ESTRUTURADOS (SQL):
{sql_data}

CONTEXTO SEMÂNTICO (RAG):
{rag_context}

Gere uma resposta natural, completa e bem formatada que combine ambas as fontes de informação.
Use markdown para formatação (negrito, listas, etc).

Resposta:""")
    
    try:
        response = llm.invoke(prompt.format(
            question=question,
            sql_data=json.dumps(sql_data, ensure_ascii=False, indent=2),
            rag_context=rag_response
        ))
        return response.content
    except Exception as e:
        print(f"❌ Erro ao combinar respostas: {e}")
        # Fallback: retorna SQL formatado
        return format_sql_results(sql_data, question)
