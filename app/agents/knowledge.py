"""
Base de Conhecimento (Knowledge) nativa do Agno para o Catálogo de Produtos.

Este módulo substitui o antigo RAG baseado em LangChain por uma implementação
100% Agno, mais eficiente e integrada ao agente.

Funcionalidades:
- Conexão com ChromaDB via Agno
- Embeddings via Google Gemini (text-embedding-004)
- Indexação automática de produtos do SQL para VectorDB
"""

import os

# ✅ CORREÇÃO: Agno 2.3 usa Knowledge, não KnowledgeBase
from agno.knowledge import Knowledge
from agno.knowledge.document import Document
from agno.knowledge.embedder.google import GeminiEmbedder
from agno.vectordb.chroma import ChromaDb
from sqlmodel import Session, select

from app.core.database import engine
from app.models.models import Produto

# Diretório para persistir embeddings (mantendo compatibilidade de caminho)
# Diretório para persistir embeddings (Volume persistente dedicado do Docker)
CHROMA_PERSIST_DIR = "/data/chroma"

def get_product_documents() -> list[Document]:
    """Gera lista de documentos Agno a partir dos produtos no banco de dados."""
    documents = []
    with Session(engine) as session:
        products = session.exec(select(Produto)).all()

        if not products:
            print("⚠️ [Knowledge] Nenhum produto encontrado para indexação")
            return []

        for p in products:
            # Determina status do estoque
            estoque_status = "ESTOQUE BAIXO - CRÍTICO" if p.estoque_atual <= p.estoque_minimo else "Estoque normal"
            diferenca = p.estoque_atual - p.estoque_minimo

            # Conteúdo enriquecido para RAG
            content = (
                f"Produto: {p.nome}\n"
                f"SKU: {p.sku}\n"
                f"Categoria: {p.categoria or 'N/A'}\n"
                f"Estoque Atual: {p.estoque_atual} unidades\n"
                f"Estoque Mínimo: {p.estoque_minimo} unidades\n"
                f"Status: {estoque_status}\n"
                f"Preço Base (BRL): {p.precos[0].preco if p.precos else 'N/A'}\n"
            )

            if p.estoque_atual <= p.estoque_minimo:
                content += f"⚠️ ATENÇÃO: Reposição necessária! Faltam {abs(diferenca)} unidades.\n"

            # Metadados para filtragem posterior
            metadata = {
                "product_id": p.id,
                "sku": p.sku,
                "nome": p.nome,
                "categoria": p.categoria or "N/A",
                "estoque_baixo": p.estoque_atual <= p.estoque_minimo
            }

            documents.append(Document(content=content, name=p.sku, meta_data=metadata))

    return documents

# Singleton para evitar recriação do cliente ChromaDb (o que causa erro 'Instance already exists')
_knowledge_instance = None

def get_product_knowledge() -> Knowledge:
    """
    Retorna o objeto Knowledge configurado para o Agno Agent.
    Usa cache para garantir Singleton e evitar conflitos do ChromaDB.

    IMPORTANTE: Usa o VectorDBManager singleton para evitar conflitos
    de múltiplas instâncias do ChromaDB.
    """
    global _knowledge_instance
    if _knowledge_instance:
        return _knowledge_instance

    # 1. Configurar Embedder Google Gemini
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("❌ GOOGLE_API_KEY não encontrada no ambiente.")

    embedder = GeminiEmbedder(
        id="models/text-embedding-004",
        api_key=api_key,
        dimensions=768  # text-embedding-004 dimensão padrão
    )

    # 2. Usar cliente ChromaDB do singleton (evita conflito de instâncias)
    try:
        from app.core.vector_db import VectorDBManager

        # Obtém o cliente singleton
        chroma_client = VectorDBManager.get_client()

        # Configura ChromaDb do Agno
        vector_db = ChromaDb(
            collection="products_agno",
            embedder=embedder,
        )
        # Injeção manual do cliente singleton (contorna a limitação do construtor do Agno)
        vector_db._client = chroma_client
    except ImportError:
        # Fallback: criar novo cliente (pode conflitar)
        vector_db = ChromaDb(
            collection="products_agno",
            path=CHROMA_PERSIST_DIR,
            embedder=embedder,
            persistent_client=True
        )

    # 3. Criar Knowledge
    _knowledge_instance = Knowledge(
        vector_db=vector_db,
    )

    return _knowledge_instance


def reset_knowledge_singleton() -> None:
    """
    Resets the Knowledge singleton to allow a fresh ChromaDB client to be created.

    This should be called after clearing the ChromaDB directory to ensure the
    next call to get_product_knowledge() creates a new client instead of
    reusing a stale connection to a deleted database file.
    """
    global _knowledge_instance
    _knowledge_instance = None


def load_knowledge_base() -> Knowledge:
    """Função utilitária para inicializar e carregar a base de conhecimento."""
    # Obter instância (Singleton)
    kb = get_product_knowledge()

    # Nota: A carga de dados (upsert) deve ser feita apenas se necessário.
    # Como check rápido, podemos ver se já existem docs.
    # Mas para garantir funcionalidade, vamos assumir que a indexação é feita por tarefa separada
    # ou deixar como estava (chamando get_product_documents).

    # Se quiser recarregar/atualizar, pode descomentar abaixo.
    # Por padrão, vamos só retornar a instância para o agente usar.

    # print("🔄 [Knowledge] Inicializando Base de Conhecimento Agno...")
    # docs = get_product_documents()
    # if docs:
    #     kb.vector_db.upsert(documents=docs)

    return kb
