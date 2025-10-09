"""Serviço de RAG (Retrieval Augmented Generation) para o chat."""

from __future__ import annotations
import os
from pathlib import Path
from typing import List, Dict, Any
import chromadb
from chromadb.config import Settings
from openai import OpenAI as OpenAIClient
from sqlmodel import Session, select
from app.models.models import ChatMessage, Produto, OrdemDeCompra

# Diretório para persistir embeddings
CHROMA_PERSIST_DIR = Path(__file__).resolve().parents[2] / "data" / "chroma"
CHROMA_PERSIST_DIR.mkdir(parents=True, exist_ok=True)

# Cliente OpenAI global para embeddings
_openai_client = None


def _get_openai_client() -> OpenAIClient:
    """Retorna cliente OpenAI configurado para OpenRouter."""
    global _openai_client
    if _openai_client is None:
        api_key = os.getenv("OPENROUTER_API_KEY")
        base_url = os.getenv("OPENROUTER_API_BASE", "https://openrouter.ai/api/v1")
        _openai_client = OpenAIClient(api_key=api_key, base_url=base_url)
    return _openai_client


def _get_embedding(text: str) -> List[float]:
    """Gera embedding para um texto usando OpenRouter."""
    try:
        client = _get_openai_client()
        response = client.embeddings.create(
            model="text-embedding-3-small",
            input=text
        )
        return response.data[0].embedding
    except Exception as e:
        print(f"Erro ao gerar embedding: {e}")
        # Fallback: retorna vetor zero
        return [0.0] * 1536


def _get_chroma_client() -> chromadb.Client:
    """Retorna cliente ChromaDB."""
    return chromadb.PersistentClient(
        path=str(CHROMA_PERSIST_DIR),
        settings=Settings(anonymized_telemetry=False)
    )


def _get_or_create_collection(collection_name: str):
    """Retorna ou cria uma collection no ChromaDB."""
    client = _get_chroma_client()
    return client.get_or_create_collection(name=collection_name)


def index_chat_message(message: ChatMessage):
    """Indexa uma mensagem do chat no vector store."""
    collection = _get_or_create_collection("chat_history")
    
    # Gera embedding
    embedding = _get_embedding(message.content)
    
    # Adiciona à collection
    collection.add(
        ids=[f"msg_{message.id}"],
        embeddings=[embedding],
        documents=[message.content],
        metadatas=[{
            "message_id": message.id,
            "session_id": message.session_id,
            "sender": message.sender,
            "timestamp": message.criado_em.isoformat(),
            "metadata": message.metadata_json or "{}"
        }]
    )


def index_product_catalog(db_session: Session):
    """Indexa todo o catálogo de produtos no vector store."""
    collection = _get_or_create_collection("products")
    
    products = db_session.exec(select(Produto)).all()
    
    if not products:
        return
    
    ids = []
    embeddings = []
    documents = []
    metadatas = []
    
    for product in products:
        content = (
            f"Produto: {product.nome}\n"
            f"SKU: {product.sku}\n"
            f"Categoria: {product.categoria or 'N/A'}\n"
            f"Estoque Atual: {product.estoque_atual}\n"
            f"Estoque Mínimo: {product.estoque_minimo}\n"
        )
        
        ids.append(f"prod_{product.id}")
        embeddings.append(_get_embedding(content))
        documents.append(content)
        metadatas.append({
            "product_id": product.id,
            "sku": product.sku,
            "nome": product.nome,
            "estoque_atual": product.estoque_atual,
            "estoque_minimo": product.estoque_minimo
        })
    
    collection.add(
        ids=ids,
        embeddings=embeddings,
        documents=documents,
        metadatas=metadatas
    )


def semantic_search_messages(query: str, session_id: int = None, k: int = 5) -> List[Dict[str, Any]]:
    """Busca semântica nas mensagens do chat."""
    collection = _get_or_create_collection("chat_history")
    
    # Gera embedding da query
    query_embedding = _get_embedding(query)
    
    # Filtro por sessão se especificado
    where_filter = {"session_id": session_id} if session_id else None
    
    try:
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=k,
            where=where_filter
        )
        
        # Formata resultados
        formatted_results = []
        if results and results['documents']:
            for idx in range(len(results['documents'][0])):
                formatted_results.append({
                    "content": results['documents'][0][idx],
                    "metadata": results['metadatas'][0][idx] if results['metadatas'] else {},
                    "score": results['distances'][0][idx] if results['distances'] else 0.0
                })
        
        return formatted_results
    except Exception as e:
        print(f"Erro na busca semântica: {e}")
        return []


def get_relevant_context(query: str, db_session: Session) -> str:
    """Obtém contexto relevante usando RAG para enriquecer a conversa."""
    
    # 1. Busca em mensagens anteriores
    chat_results = semantic_search_messages(query, k=3)
    
    # 2. Busca em produtos
    try:
        product_collection = _get_or_create_collection("products")
        query_embedding = _get_embedding(query)
        product_results = product_collection.query(
            query_embeddings=[query_embedding],
            n_results=3
        )
    except Exception as e:
        print(f"Erro ao buscar produtos: {e}")
        product_results = None
    
    # 3. Monta contexto
    context_parts = []
    
    if chat_results:
        context_parts.append("### Conversas Anteriores Relevantes:")
        for result in chat_results:
            context_parts.append(f"- {result['content']}")
    
    if product_results and product_results.get('documents'):
        context_parts.append("\n### Produtos Relacionados:")
        for doc in product_results['documents'][0]:
            context_parts.append(f"- {doc}")
    
    return "\n".join(context_parts) if context_parts else ""


def embed_and_store_message(message: ChatMessage):
    """Wrapper assíncrono para indexar mensagem."""
    try:
        index_chat_message(message)
    except Exception as e:
        # Log error mas não quebra o fluxo
        print(f"Erro ao indexar mensagem: {e}")
