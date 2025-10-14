"""
Serviço de RAG construído com LangChain e 100% no ecossistema Google AI 2.5.
Atua como a base de conhecimento especialista em produtos.

ARQUITETURA HÍBRIDA (2025-10-14):
===================================
✅ Framework: LangChain para pipeline RAG estruturado
✅ Embeddings: Google text-embedding-004 (768 dimensões)
✅ LLM: Google Gemini 2.5 Flash (gemini-2.5-flash-latest)
✅ Vector Store: ChromaDB (persistente)
✅ Integração: Expõe funções simples para o Agno Agent

MODELOS GOOGLE AI 2.5:
=======================
• Embeddings: models/text-embedding-004
• LLM RAG: gemini-2.5-flash-latest (temp=0.1 para precisão)

REFERÊNCIAS:
- LangChain: https://docs.langchain.com/
- Google AI: https://ai.google.dev/
- Agno Integration: https://docs.agno.com/
"""

from __future__ import annotations
import os
from pathlib import Path
from typing import List, Dict, Any

from langchain_core.documents import Document
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_community.vectorstores import Chroma
from langchain_google_genai import GoogleGenerativeAIEmbeddings, ChatGoogleGenerativeAI
from sqlmodel import Session, select

from app.models.models import Produto, ChatMessage

# Diretório para persistir embeddings
CHROMA_PERSIST_DIR = str(Path(__file__).resolve().parents[2] / "data" / "chroma")

# Validação crítica da API Key
if not os.getenv("GOOGLE_API_KEY"):
    raise RuntimeError(
        "❌ GOOGLE_API_KEY não encontrada no ambiente.\n"
        "Configure no .env: GOOGLE_API_KEY=sua_chave_aqui\n"
        "Obtenha em: https://aistudio.google.com/app/apikey"
    )

# Embeddings globais (reutilizados em todas as operações)
google_embeddings = GoogleGenerativeAIEmbeddings(
    model="models/text-embedding-004"
)


def get_vector_store() -> Chroma:
    """
    Retorna instância do vector store ChromaDB configurado com embeddings do Google.
    
    Returns:
        Chroma: Vector store pronto para uso
    """
    return Chroma(
        collection_name="products",
        persist_directory=CHROMA_PERSIST_DIR,
        embedding_function=google_embeddings
    )


def index_product_catalog(db_session: Session) -> None:
    """
    Indexa todo o catálogo de produtos no vector store usando LangChain.
    
    Processo:
    1. Carrega produtos do banco de dados
    2. Cria documentos estruturados
    3. Gera embeddings com Google AI
    4. Persiste no ChromaDB
    
    Args:
        db_session: Sessão ativa do banco de dados
    """
    products = db_session.exec(select(Produto)).all()
    
    if not products:
        print("⚠️ [RAG Service] Nenhum produto encontrado para indexação")
        return
    
    # Cria documentos LangChain a partir dos produtos
    documents = [
        Document(
            page_content=(
                f"Produto: {p.nome}\n"
                f"SKU: {p.sku}\n"
                f"Categoria: {p.categoria or 'N/A'}\n"
                f"Estoque Atual: {p.estoque_atual} unidades\n"
                f"Estoque Mínimo: {p.estoque_minimo} unidades"
            ),
            metadata={
                "product_id": p.id,
                "sku": p.sku,
                "nome": p.nome,
                "categoria": p.categoria or "N/A",
                "estoque_atual": p.estoque_atual,
                "estoque_minimo": p.estoque_minimo
            }
        )
        for p in products
    ]
    
    if documents:
        vector_store = get_vector_store()
        vector_store.add_documents(documents)
        print(f"✅ [RAG Service] {len(documents)} produtos indexados com embeddings Google AI")


def create_rag_chain():
    """
    Cria a chain RAG completa usando LangChain com Google AI 2.5.
    
    Pipeline (LangChain LCEL):
    1. Retriever: Busca documentos relevantes (top-k=5) usando ChromaDB
    2. Prompt: Template especializado para produtos industriais
    3. LLM: Gemini 2.5 Flash (gemini-2.5-flash-latest, temp=0.1)
    4. Parser: Converte resposta para string limpa
    
    Returns:
        Runnable: Chain executável do LangChain (LCEL)
        
    Notas:
        - Usa embeddings text-embedding-004 para busca semântica
        - LLM com temperatura baixa (0.1) para respostas factuais precisas
        - Pipeline otimizado para latência mínima com máxima precisão
    """
    # 1. Configurar retriever com busca top-5
    retriever = get_vector_store().as_retriever(
        search_kwargs={'k': 5}
    )
    
    # 2. Template de prompt otimizado para catálogo de produtos
    template = """Você é um sistema especialista em responder perguntas sobre um catálogo de produtos industriais.

**REGRAS IMPORTANTES:**
1. Use APENAS as informações do CONTEXTO abaixo como fonte de verdade
2. Responda de forma concisa e direta
3. Se a informação não estiver no contexto, diga claramente que não encontrou
4. Mantenha um tom profissional e prestativo
5. Sempre cite o SKU quando falar de um produto específico

CONTEXTO:
{context}

PERGUNTA:
{question}

Resposta:"""
    
    prompt = ChatPromptTemplate.from_template(template)
    
    # 3. LLM do Google (Gemini 2.5 Flash - máxima performance)
    llm = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash-latest",
        temperature=0.1  # Quase determinístico para respostas factuais precisas
    )
    
    # 4. Função helper para formatar documentos
    def format_docs(docs: List[Document]) -> str:
        """Formata lista de documentos em texto único."""
        return "\n\n".join(doc.page_content for doc in docs)
    
    # 5. Monta a chain LCEL (LangChain Expression Language)
    rag_chain = (
        {"context": retriever | format_docs, "question": RunnablePassthrough()}
        | prompt
        | llm
        | StrOutputParser()
    )
    
    return rag_chain


def query_product_catalog_with_google_rag(query: str) -> str:
    """
    Interface principal para consultas RAG ao catálogo de produtos.
    
    Esta é a função que deve ser chamada pelas ferramentas Agno.
    
    Args:
        query: Pergunta em linguagem natural sobre produtos
        
    Returns:
        str: Resposta gerada pelo RAG baseada no contexto relevante
        
    Example:
        >>> query_product_catalog_with_google_rag("Qual o estoque da Parafusadeira Makita?")
        "A Parafusadeira Makita (SKU_005) possui atualmente 45 unidades em estoque..."
    """
    try:
        rag_chain = create_rag_chain()
        response = rag_chain.invoke(query)
        return response
    except Exception as e:
        error_msg = f"❌ Erro ao consultar catálogo: {str(e)}"
        print(error_msg)
        return error_msg


# ============================================================================
# FUNÇÕES DE COMPATIBILIDADE (mantidas do código legado)
# ============================================================================

def index_chat_message(message: ChatMessage) -> None:
    """
    Indexa mensagem de chat (funcionalidade legada mantida).
    
    NOTA: Esta função usa a implementação antiga com ChromaDB direto.
    Pode ser refatorada futuramente para usar LangChain completamente.
    """
    try:
        import chromadb
        from chromadb.config import Settings
        
        client = chromadb.PersistentClient(
            path=CHROMA_PERSIST_DIR,
            settings=Settings(anonymized_telemetry=False)
        )
        
        collection = client.get_or_create_collection(name="chat_history")
        
        # Gera embedding usando o mesmo modelo
        embedding = google_embeddings.embed_query(message.content)
        
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
    except Exception as e:
        print(f"⚠️ Erro ao indexar mensagem: {e}")


def get_relevant_context(query: str, db_session: Session) -> str:
    """
    Obtém contexto relevante (funcionalidade legada mantida).
    
    NOTA: Mantida para compatibilidade com conversational_agent.py
    """
    try:
        # Busca produtos relevantes usando RAG
        response = query_product_catalog_with_google_rag(query)
        
        if response and not response.startswith("❌"):
            return f"### Informações Relevantes do Catálogo:\n{response}"
        else:
            return ""
    except Exception as e:
        print(f"⚠️ Erro ao buscar contexto: {e}")
        return ""


def embed_and_store_message(message: ChatMessage) -> None:
    """Wrapper para indexar mensagem (compatibilidade)."""
    try:
        index_chat_message(message)
    except Exception as e:
        print(f"⚠️ Erro ao armazenar mensagem: {e}")
