"""
Serviço de RAG (Retrieval-Augmented Generation) com LangChain e Google AI.

ARQUITETURA DE PRODUÇÃO:
========================
- Vector Store: ChromaDB via singleton (app.core.vector_db)
- Embeddings: Google text-embedding-004
- LLM: Google Gemini 2.5 Flash
- Framework: LangChain LCEL

MUDANÇAS (2026-01-14):
- Removida indexação do startup (movida para /admin/rag/sync)
- Usa singleton VectorDBManager em vez de criar instâncias
- Lazy loading de embeddings e LLM

REFERÊNCIAS:
- LangChain RAG: https://python.langchain.com/docs/tutorials/rag/
- Google AI: https://ai.google.dev/
- ChromaDB: https://docs.trychroma.com/

Autor: Sistema PMI | Data: 2026-01-14
"""

from __future__ import annotations

import logging
import os
from typing import List, Optional

from langchain_core.documents import Document
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_chroma import Chroma
from langchain_google_genai import GoogleGenerativeAIEmbeddings, ChatGoogleGenerativeAI
from sqlmodel import Session

from app.models.models import Produto, ChatMessage

LOGGER = logging.getLogger(__name__)


# ============================================================================
# VALIDAÇÃO DE AMBIENTE (Fail-Fast)
# ============================================================================

def _validate_google_api_key() -> None:
    """Valida presença da API key no startup."""
    if not os.getenv("GOOGLE_API_KEY"):
        raise RuntimeError(
            "❌ GOOGLE_API_KEY não encontrada no ambiente.\n"
            "Configure no .env: GOOGLE_API_KEY=sua_chave_aqui\n"
            "Obtenha em: https://aistudio.google.com/app/apikey"
        )


# Validação no import
_validate_google_api_key()


# ============================================================================
# LAZY LOADING (Evita instanciar no import)
# ============================================================================

_embeddings: Optional[GoogleGenerativeAIEmbeddings] = None
_vector_store: Optional[Chroma] = None


def get_embeddings() -> GoogleGenerativeAIEmbeddings:
    """
    Retorna instância singleton dos embeddings Google AI.
    
    Lazy loading: só instancia quando necessário.
    """
    global _embeddings
    if _embeddings is None:
        _embeddings = GoogleGenerativeAIEmbeddings(
            model="models/text-embedding-004"
        )
        LOGGER.info("✅ Google Embeddings inicializados")
    return _embeddings


def get_vector_store() -> Chroma:
    """
    Retorna instância do vector store ChromaDB (LangChain).
    
    Usa o singleton VectorDBManager para evitar conflitos de instância.
    """
    global _vector_store
    if _vector_store is None:
        from app.core.vector_db import get_vector_db_client
        
        # Obtém cliente singleton
        client = get_vector_db_client()
        
        # Cria wrapper LangChain usando o cliente existente
        _vector_store = Chroma(
            client=client,
            collection_name="products",
            embedding_function=get_embeddings()
        )
        LOGGER.info("✅ LangChain Chroma conectado ao singleton")
    
    return _vector_store


# ============================================================================
# RAG CHAIN
# ============================================================================

# Template de prompt especializado
RAG_PROMPT_TEMPLATE = """Você é um sistema especialista em responder perguntas sobre um catálogo de produtos industriais.

**REGRAS IMPORTANTES:**
1. Use APENAS as informações do CONTEXTO abaixo como fonte de verdade
2. Responda de forma concisa, clara e bem formatada (use markdown: negrito, listas)
3. Se a informação não estiver no contexto, diga claramente que não encontrou
4. Mantenha um tom profissional e prestativo
5. Sempre cite o SKU quando falar de um produto específico
6. Para perguntas sobre "estoque baixo", procure por produtos com status "ESTOQUE BAIXO - CRÍTICO"
7. Liste TODOS os produtos relevantes encontrados no contexto
8. Se houver dados estruturados (JSON) na pergunta, use-os para enriquecer sua resposta
9. Organize a resposta de forma clara: use títulos, listas e destaque informações importantes

CONTEXTO:
{context}

PERGUNTA:
{question}

Resposta (use markdown para formatação):"""


def _format_docs(docs: List[Document]) -> str:
    """Formata lista de documentos em texto único."""
    return "\n\n".join(doc.page_content for doc in docs)


def create_rag_chain(k: int = 20):
    """
    Cria a chain RAG completa usando LangChain LCEL.
    
    Args:
        k: Número de documentos a recuperar
        
    Returns:
        Runnable: Chain executável
    """
    # Retriever
    retriever = get_vector_store().as_retriever(
        search_kwargs={'k': k}
    )
    
    # Prompt
    prompt = ChatPromptTemplate.from_template(RAG_PROMPT_TEMPLATE)
    
    # LLM (Gemini 2.5 Flash - alta performance)
    llm = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        temperature=0.1  # Quase determinístico para respostas factuais
    )
    
    # Chain LCEL
    rag_chain = (
        {"context": retriever | _format_docs, "question": RunnablePassthrough()}
        | prompt
        | llm
        | StrOutputParser()
    )
    
    return rag_chain


# ============================================================================
# INTERFACE PRINCIPAL
# ============================================================================

def query_product_catalog_with_google_rag(query: str, k: int = 20) -> str:
    """
    Interface principal para consultas RAG ao catálogo de produtos.
    
    Esta é a função que deve ser chamada pelas ferramentas Agno.
    
    Args:
        query: Pergunta em linguagem natural sobre produtos
        k: Número de documentos a recuperar (padrão: 20)
        
    Returns:
        str: Resposta gerada pelo RAG baseada no contexto relevante
        
    Example:
        >>> query_product_catalog_with_google_rag("Qual o estoque da Parafusadeira?")
        "A Parafusadeira (SKU_005) possui atualmente 45 unidades em estoque..."
    """
    try:
        rag_chain = create_rag_chain(k=k)
        response = rag_chain.invoke(query)
        return response
    except Exception as e:
        error_msg = f"❌ Erro ao consultar catálogo: {str(e)}"
        LOGGER.error(error_msg, exc_info=True)
        return error_msg


# ============================================================================
# FUNÇÕES DE INDEXAÇÃO (Usadas pelo admin_router)
# ============================================================================

def index_product(product: Produto) -> None:
    """
    Indexa um único produto no vector store.
    
    Args:
        product: Produto a indexar
    """
    vector_store = get_vector_store()
    
    # Cria documento enriquecido
    estoque_status = "ESTOQUE BAIXO - CRÍTICO" if product.estoque_atual <= product.estoque_minimo else "Estoque normal"
    
    content = (
        f"Produto: {product.nome}\n"
        f"SKU: {product.sku}\n"
        f"Categoria: {product.categoria or 'N/A'}\n"
        f"Estoque Atual: {product.estoque_atual} unidades\n"
        f"Estoque Mínimo: {product.estoque_minimo} unidades\n"
        f"Status: {estoque_status}\n"
    )
    
    if product.estoque_atual <= product.estoque_minimo:
        diferenca = product.estoque_minimo - product.estoque_atual
        content += f"⚠️ ATENÇÃO: Faltam {diferenca} unidades para atingir o estoque mínimo.\n"
    
    doc = Document(
        page_content=content,
        metadata={
            "product_id": product.id,
            "sku": product.sku,
            "nome": product.nome,
            "categoria": product.categoria or "N/A",
            "estoque_atual": product.estoque_atual,
            "estoque_minimo": product.estoque_minimo,
            "estoque_baixo": product.estoque_atual <= product.estoque_minimo
        }
    )
    
    vector_store.add_documents([doc], ids=[f"product_{product.id}"])


def index_product_catalog(db_session: Session) -> int:
    """
    Indexa todo o catálogo de produtos (DEPRECADO: use /admin/rag/sync).
    
    Esta função ainda funciona mas carrega TODOS os produtos na RAM.
    Para produção, use o endpoint /admin/rag/sync que faz paginação.
    
    Args:
        db_session: Sessão do banco de dados
        
    Returns:
        int: Número de produtos indexados
    """
    from sqlmodel import select
    
    LOGGER.warning(
        "⚠️ index_product_catalog() está deprecado. "
        "Use POST /admin/rag/sync para indexação paginada."
    )
    
    products = db_session.exec(select(Produto)).all()
    
    if not products:
        LOGGER.warning("Nenhum produto encontrado para indexação")
        return 0
    
    for product in products:
        try:
            index_product(product)
        except Exception as e:
            LOGGER.error(f"Erro ao indexar {product.sku}: {e}")
    
    LOGGER.info(f"✅ {len(products)} produtos indexados")
    return len(products)


# ============================================================================
# FUNÇÕES DE COMPATIBILIDADE (Legado)
# ============================================================================

def index_chat_message(message: ChatMessage) -> None:
    """
    Indexa mensagem de chat (funcionalidade legada mantida).
    """
    try:
        from app.core.vector_db import get_vector_db_client
        
        client = get_vector_db_client()
        collection = client.get_or_create_collection(name="chat_history")
        
        # Gera embedding
        embedding = get_embeddings().embed_query(message.content)
        
        collection.add(
            ids=[f"msg_{message.id}"],
            embeddings=[embedding],
            documents=[message.content],
            metadatas=[{
                "message_id": message.id,
                "session_id": message.session_id,
                "sender": message.sender,
                "timestamp": message.criado_em.isoformat(),
            }]
        )
    except Exception as e:
        LOGGER.warning(f"Erro ao indexar mensagem: {e}")


def get_relevant_context(query: str, db_session: Session) -> str:
    """
    Obtém contexto relevante (funcionalidade legada mantida).
    """
    try:
        response = query_product_catalog_with_google_rag(query)
        
        if response and not response.startswith("❌"):
            return f"### Informações Relevantes do Catálogo:\n{response}"
        return ""
    except Exception as e:
        LOGGER.warning(f"Erro ao buscar contexto: {e}")
        return ""


def embed_and_store_message(message: ChatMessage) -> None:
    """Wrapper para indexar mensagem (compatibilidade)."""
    try:
        index_chat_message(message)
    except Exception as e:
        LOGGER.warning(f"Erro ao armazenar mensagem: {e}")


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    "get_vector_store",
    "get_embeddings",
    "create_rag_chain",
    "query_product_catalog_with_google_rag",
    "index_product",
    "index_product_catalog",
    "index_chat_message",
    "get_relevant_context",
    "embed_and_store_message",
]
