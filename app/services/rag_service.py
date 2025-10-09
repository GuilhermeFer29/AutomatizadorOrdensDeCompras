"""Serviço de RAG (Retrieval Augmented Generation) para o chat."""

from __future__ import annotations
import os
from pathlib import Path
from typing import List, Dict, Any
from langchain_chroma import Chroma
from langchain_openai import OpenAIEmbeddings
from langchain_core.documents import Document
from sqlmodel import Session, select
from app.models.models import ChatMessage, Produto, OrdemDeCompra

# Diretório para persistir embeddings
CHROMA_PERSIST_DIR = Path(__file__).resolve().parents[2] / "data" / "chroma"
CHROMA_PERSIST_DIR.mkdir(parents=True, exist_ok=True)


def _get_embeddings():
    """Retorna modelo de embeddings usando OpenRouter."""
    api_key = os.getenv("OPENROUTER_API_KEY")
    base_url = os.getenv("OPENROUTER_API_BASE", "https://openrouter.ai/api/v1")
    
    return OpenAIEmbeddings(
        model="text-embedding-3-small",
        openai_api_key=api_key,
        base_url=base_url
    )


def _get_vector_store(collection_name: str = "chat_history") -> Chroma:
    """Retorna ou cria vector store para o chat."""
    return Chroma(
        collection_name=collection_name,
        embedding_function=_get_embeddings(),
        persist_directory=str(CHROMA_PERSIST_DIR)
    )


def index_chat_message(message: ChatMessage):
    """Indexa uma mensagem do chat no vector store."""
    vector_store = _get_vector_store()
    
    # Cria documento com metadados
    doc = Document(
        page_content=message.content,
        metadata={
            "message_id": message.id,
            "session_id": message.session_id,
            "sender": message.sender,
            "timestamp": message.criado_em.isoformat(),
            "metadata": message.metadata_json or "{}"
        }
    )
    
    vector_store.add_documents([doc])


def index_product_catalog(db_session: Session):
    """Indexa todo o catálogo de produtos no vector store."""
    vector_store = _get_vector_store(collection_name="products")
    
    products = db_session.exec(select(Produto)).all()
    
    documents = []
    for product in products:
        content = (
            f"Produto: {product.nome}\n"
            f"SKU: {product.sku}\n"
            f"Categoria: {product.categoria or 'N/A'}\n"
            f"Estoque Atual: {product.estoque_atual}\n"
            f"Estoque Mínimo: {product.estoque_minimo}\n"
        )
        
        doc = Document(
            page_content=content,
            metadata={
                "product_id": product.id,
                "sku": product.sku,
                "nome": product.nome,
                "estoque_atual": product.estoque_atual,
                "estoque_minimo": product.estoque_minimo
            }
        )
        documents.append(doc)
    
    if documents:
        vector_store.add_documents(documents)


def semantic_search_messages(query: str, session_id: int = None, k: int = 5) -> List[Dict[str, Any]]:
    """Busca semântica nas mensagens do chat."""
    vector_store = _get_vector_store()
    
    # Filtro por sessão se especificado
    filter_dict = {"session_id": session_id} if session_id else None
    
    results = vector_store.similarity_search_with_score(
        query,
        k=k,
        filter=filter_dict
    )
    
    return [
        {
            "content": doc.page_content,
            "metadata": doc.metadata,
            "score": float(score)
        }
        for doc, score in results
    ]


def get_relevant_context(query: str, db_session: Session) -> str:
    """Obtém contexto relevante usando RAG para enriquecer a conversa."""
    
    # 1. Busca em mensagens anteriores
    chat_results = semantic_search_messages(query, k=3)
    
    # 2. Busca em produtos
    product_store = _get_vector_store(collection_name="products")
    product_results = product_store.similarity_search(query, k=3)
    
    # 3. Monta contexto
    context_parts = []
    
    if chat_results:
        context_parts.append("### Conversas Anteriores Relevantes:")
        for result in chat_results:
            context_parts.append(f"- {result['content']}")
    
    if product_results:
        context_parts.append("\n### Produtos Relacionados:")
        for doc in product_results:
            context_parts.append(f"- {doc.page_content}")
    
    return "\n".join(context_parts) if context_parts else ""


def embed_and_store_message(message: ChatMessage):
    """Wrapper assíncrono para indexar mensagem."""
    try:
        index_chat_message(message)
    except Exception as e:
        # Log error mas não quebra o fluxo
        print(f"Erro ao indexar mensagem: {e}")
