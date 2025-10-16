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
3. Ou se precisa de ambos (híbrido)

PERGUNTA: {question}

Retorne um JSON com:
{{
    "query_type": "sql" | "rag" | "hybrid",
    "needs_stock_filter": true/false,
    "stock_filter_type": "low" | "high" | "all" | null,
    "needs_category_filter": true/false,
    "category": "categoria" | null,
    "needs_sorting": true/false,
    "sort_by": "stock_asc" | "stock_desc" | null,
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
    
    # 2. Executa consulta SQL se necessário
    sql_results = None
    if query_type in ["sql", "hybrid"]:
        sql_results = execute_sql_query(intent, db_session)
        print(f"📊 SQL retornou {len(sql_results) if isinstance(sql_results, list) else 'dados'}")
    
    # 3. Executa RAG se necessário
    rag_response = None
    if query_type in ["rag", "hybrid"]:
        from app.services.rag_service import query_product_catalog_with_google_rag
        
        # Se tem resultados SQL, enriquece a pergunta com contexto
        if sql_results:
            enhanced_query = f"{user_question}\n\nDados estruturados disponíveis: {json.dumps(sql_results, ensure_ascii=False)}"
            rag_response = query_product_catalog_with_google_rag(enhanced_query)
        else:
            rag_response = query_product_catalog_with_google_rag(user_question)
        
        print(f"🤖 RAG respondeu: {rag_response[:100]}...")
    
    # 4. Combina resultados e gera resposta final
    return format_final_response(user_question, sql_results, rag_response, intent)


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


def format_final_response(
    question: str,
    sql_results: Any,
    rag_response: str,
    intent: Dict[str, Any]
) -> str:
    """
    Formata resposta final combinando SQL e RAG.
    """
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
