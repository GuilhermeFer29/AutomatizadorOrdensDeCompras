"""
Script para RECRIAR o RAG completo incluindo fornecedores e ofertas.

Este script:
1. Limpa o vector store existente
2. Indexa produtos com informações de:
   - Dados básicos (nome, SKU, estoque)
   - Ofertas de fornecedores (preços, prazos, confiabilidade)
   - Histórico de vendas
   - Previsões ML (se disponível)

Uso:
    docker compose exec api python scripts/rebuild_rag_with_suppliers.py
"""

from __future__ import annotations
import sys
import logging
from pathlib import Path
from typing import List

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv
from sqlmodel import Session, select
from langchain.docstore.document import Document

from app.core.database import engine
from app.models.models import Produto, Fornecedor, OfertaProduto, VendasHistoricas
from app.services.rag_service import get_vector_store

LOGGER = logging.getLogger(__name__)


def clear_vector_store():
    """Limpa completamente o vector store existente."""
    try:
        vector_store = get_vector_store()
        # ChromaDB permite deletar a coleção inteira
        vector_store._client.delete_collection(vector_store._collection_name)
        LOGGER.info("🗑️ Vector store limpo com sucesso")
    except Exception as e:
        LOGGER.warning(f"⚠️ Erro ao limpar vector store (pode ser primeira execução): {e}")


def get_product_sales_summary(session: Session, produto_id: int) -> str:
    """Obtém resumo de vendas de um produto."""
    vendas = session.exec(
        select(VendasHistoricas)
        .where(VendasHistoricas.produto_id == produto_id)
        .order_by(VendasHistoricas.data_venda.desc())
        .limit(100)
    ).all()
    
    if not vendas:
        return "Sem histórico de vendas"
    
    total_vendido = sum(v.quantidade for v in vendas)
    receita_total = sum(v.receita for v in vendas)
    
    return f"Total vendido: {total_vendido} unidades | Receita: R$ {receita_total:,.2f}"


def get_supplier_offers(session: Session, produto_id: int) -> List[dict]:
    """Obtém ofertas de fornecedores para um produto."""
    ofertas = session.exec(
        select(OfertaProduto, Fornecedor)
        .where(OfertaProduto.produto_id == produto_id)
        .join(Fornecedor, OfertaProduto.fornecedor_id == Fornecedor.id)
        .order_by(OfertaProduto.preco_ofertado)
    ).all()
    
    offers_list = []
    for oferta, fornecedor in ofertas:
        offers_list.append({
            "fornecedor": fornecedor.nome,
            "preco": float(oferta.preco_ofertado),
            "prazo_dias": fornecedor.prazo_entrega_dias,
            "confiabilidade": fornecedor.confiabilidade,
            "estoque_disponivel": oferta.estoque_disponivel
        })
    
    return offers_list


def create_enriched_document(produto: Produto, offers: List[dict], sales_summary: str) -> Document:
    """
    Cria um documento enriquecido com todas as informações do produto.
    
    Args:
        produto: Produto do banco
        offers: Lista de ofertas de fornecedores
        sales_summary: Resumo de vendas
    
    Returns:
        Document LangChain enriquecido
    """
    # Status do estoque
    estoque_status = "CRÍTICO - ESTOQUE BAIXO" if produto.estoque_atual <= produto.estoque_minimo else "Estoque adequado"
    diferenca = produto.estoque_atual - produto.estoque_minimo
    
    # Informações de fornecedores
    if offers:
        melhor_oferta = min(offers, key=lambda x: x["preco"])
        preco_medio = sum(o["preco"] for o in offers) / len(offers)
        
        fornecedores_info = f"\n\n📦 OFERTAS DE FORNECEDORES ({len(offers)} disponíveis):\n"
        fornecedores_info += f"Melhor preço: R$ {melhor_oferta['preco']:.2f} - {melhor_oferta['fornecedor']}\n"
        fornecedores_info += f"Preço médio: R$ {preco_medio:.2f}\n"
        fornecedores_info += f"Prazo médio: {sum(o['prazo_dias'] for o in offers) / len(offers):.0f} dias\n"
        
        # Lista top 3 ofertas
        fornecedores_info += "\nTop 3 ofertas:\n"
        for i, offer in enumerate(offers[:3], 1):
            confiabilidade_pct = offer['confiabilidade'] * 100
            fornecedores_info += (
                f"{i}. {offer['fornecedor']}: R$ {offer['preco']:.2f} "
                f"| {offer['prazo_dias']} dias | {confiabilidade_pct:.0f}% confiável\n"
            )
    else:
        fornecedores_info = "\n\n⚠️ Nenhuma oferta de fornecedor disponível para este produto"
    
    # Conteúdo completo do documento
    content = f"""
🏷️ PRODUTO: {produto.nome}
SKU: {produto.sku}
Categoria: {produto.categoria or 'Sem categoria'}

📊 ESTOQUE:
- Atual: {produto.estoque_atual} unidades
- Mínimo: {produto.estoque_minimo} unidades
- Status: {estoque_status}
"""
    
    if produto.estoque_atual <= produto.estoque_minimo:
        content += f"- ⚠️ ALERTA: Faltam {abs(diferenca)} unidades para atingir estoque mínimo!\n"
    
    content += f"\n📈 VENDAS: {sales_summary}\n"
    content += fornecedores_info
    
    # Metadata enriquecido
    metadata = {
        "product_id": produto.id,
        "sku": produto.sku,
        "nome": produto.nome,
        "categoria": produto.categoria or "N/A",
        "estoque_atual": produto.estoque_atual,
        "estoque_minimo": produto.estoque_minimo,
        "estoque_baixo": produto.estoque_atual <= produto.estoque_minimo,
        "total_fornecedores": len(offers),
        "tem_ofertas": len(offers) > 0,
    }
    
    # Adiciona informação do melhor preço se houver ofertas
    if offers:
        melhor_oferta = min(offers, key=lambda x: x["preco"])
        metadata.update({
            "melhor_preco": melhor_oferta["preco"],
            "melhor_fornecedor": melhor_oferta["fornecedor"],
            "preco_medio": sum(o["preco"] for o in offers) / len(offers),
        })
    
    return Document(
        page_content=content.strip(),
        metadata=metadata
    )


def rebuild_rag_complete(session: Session) -> None:
    """
    Reconstrói o RAG completo com todas as informações.
    
    Args:
        session: Sessão do banco de dados
    """
    LOGGER.info("🔄 Iniciando reconstrução completa do RAG...")
    
    # 1. Limpar vector store existente
    clear_vector_store()
    
    # 2. Carregar todos os produtos
    produtos = session.exec(select(Produto)).all()
    
    if not produtos:
        LOGGER.warning("⚠️ Nenhum produto encontrado no banco de dados")
        return
    
    LOGGER.info(f"📦 Processando {len(produtos)} produtos...")
    
    # 3. Criar documentos enriquecidos
    documents = []
    produtos_com_ofertas = 0
    produtos_sem_ofertas = 0
    
    for produto in produtos:
        # Buscar ofertas de fornecedores
        offers = get_supplier_offers(session, produto.id)
        
        # Buscar resumo de vendas
        sales_summary = get_product_sales_summary(session, produto.id)
        
        # Criar documento enriquecido
        doc = create_enriched_document(produto, offers, sales_summary)
        documents.append(doc)
        
        # Estatísticas
        if offers:
            produtos_com_ofertas += 1
        else:
            produtos_sem_ofertas += 1
        
        if (len(documents) % 50 == 0):
            LOGGER.info(f"   Processados {len(documents)}/{len(produtos)} produtos...")
    
    # 4. Indexar no vector store
    if documents:
        LOGGER.info(f"💾 Indexando {len(documents)} documentos no vector store...")
        vector_store = get_vector_store()
        vector_store.add_documents(documents)
        
        LOGGER.info("✅ RAG reconstruído com sucesso!")
        LOGGER.info(f"📊 Estatísticas:")
        LOGGER.info(f"   - Total de produtos: {len(produtos)}")
        LOGGER.info(f"   - Com ofertas de fornecedores: {produtos_com_ofertas}")
        LOGGER.info(f"   - Sem ofertas: {produtos_sem_ofertas}")
        LOGGER.info(f"   - Taxa de cobertura: {(produtos_com_ofertas/len(produtos)*100):.1f}%")
    else:
        LOGGER.warning("⚠️ Nenhum documento criado")


def main():
    """Função principal."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s"
    )
    load_dotenv()
    
    print("\n" + "="*70)
    print("🔄 RECONSTRUÇÃO COMPLETA DO RAG")
    print("   Incluindo: Produtos + Fornecedores + Ofertas + Vendas")
    print("="*70 + "\n")
    
    with Session(engine) as session:
        try:
            rebuild_rag_complete(session)
            print("\n✅ Processo concluído com sucesso!")
            print("   O RAG agora contém informações completas sobre:")
            print("   - Produtos e estoque")
            print("   - Ofertas de fornecedores com preços e prazos")
            print("   - Histórico de vendas")
            print("\n")
        except Exception as e:
            LOGGER.error(f"❌ Erro na reconstrução do RAG: {e}")
            import traceback
            traceback.print_exc()
            raise


if __name__ == "__main__":
    main()
