from typing import List, Optional
import logging
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query
from sqlmodel import Session, select
from app.core.database import get_session
from app.services.product_service import get_products, get_product_by_id, create_product, update_product
from app.models.models import PrecosHistoricos, Produto
from pydantic import BaseModel

logger = logging.getLogger(__name__)

class ProductCreate(BaseModel):
    sku: str
    name: str
    price: float
    stock: int

class ProductUpdate(BaseModel):
    name: Optional[str] = None
    price: Optional[float] = None
    stock: Optional[int] = None

router = APIRouter(prefix="/api/products", tags=["api-products"])


def sync_rag_background():
    """
    Função para sincronizar RAG em background após mudanças no banco.
    
    Executa a sincronização sem bloquear a resposta da API.
    """
    try:
        from app.services.rag_sync_service import trigger_rag_sync
        logger.info("🔄 Sincronizando RAG em background após mudança no banco...")
        result = trigger_rag_sync()
        if result["status"] == "success":
            logger.info(f"✅ RAG sincronizado: {result['products_indexed']} produtos")
        else:
            logger.warning(f"⚠️ Erro ao sincronizar RAG: {result['message']}")
    except Exception as e:
        logger.error(f"❌ Erro ao sincronizar RAG em background: {e}")


@router.get("/")
def read_products(search: Optional[str] = None, session: Session = Depends(get_session)):
    """
    Retorna lista de produtos com preço atual.
    """
    from sqlalchemy import func, desc
    
    produtos = get_products(session, search)
    
    result = []
    for produto in produtos:
        # Buscar preço mais recente
        preco_recente = session.exec(
            select(PrecosHistoricos)
            .where(PrecosHistoricos.produto_id == produto.id)
            .order_by(desc(PrecosHistoricos.coletado_em))
            .limit(1)
        ).first()
        
        preco_atual = float(preco_recente.preco) if preco_recente else 0.0
        
        result.append({
            "id": produto.id,
            "sku": produto.sku,
            "nome": produto.nome,
            "categoria": produto.categoria,
            "preco_atual": preco_atual,
            "estoque_atual": produto.estoque_atual,
            "estoque_minimo": produto.estoque_minimo,
            "criado_em": produto.criado_em.isoformat(),
            "atualizado_em": produto.atualizado_em.isoformat(),
        })
    
    return result


@router.get("/{product_id}")
def read_product(product_id: int, session: Session = Depends(get_session)):
    product = get_product_by_id(session, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product


@router.post("/")
def handle_create_product(
    product: ProductCreate,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session)
):
    """
    Cria um novo produto e sincroniza RAG automaticamente.
    
    A sincronização do RAG acontece em background para não atrasar a resposta.
    """
    created_product = create_product(session, product.dict())
    
    # Sincroniza RAG em background
    background_tasks.add_task(sync_rag_background)
    logger.info(f"📦 Produto criado: {product.sku} - RAG será sincronizado")
    
    return created_product


@router.put("/{product_id}")
def handle_update_product(
    product_id: int,
    product: ProductUpdate,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session)
):
    """
    Atualiza um produto e sincroniza RAG automaticamente.
    
    A sincronização do RAG acontece em background para não atrasar a resposta.
    """
    updated_product = update_product(session, product_id, product.dict(exclude_unset=True))
    if not updated_product:
        raise HTTPException(status_code=404, detail="Product not found")
    
    # Sincroniza RAG em background
    background_tasks.add_task(sync_rag_background)
    logger.info(f"🔄 Produto atualizado: ID {product_id} - RAG será sincronizado")
    
    return updated_product


@router.get("/{sku}/price-history")
def get_product_price_history(
    sku: str,
    limit: int = Query(default=30, ge=1, le=365),
    session: Session = Depends(get_session)
):
    """
    Retorna o histórico de preços de um produto por SKU.
    
    Args:
        sku: SKU do produto
        limit: Número máximo de registros (padrão: 30, máximo: 365)
    """
    # Buscar produto pelo SKU
    produto = session.exec(select(Produto).where(Produto.sku == sku)).first()
    if not produto:
        raise HTTPException(status_code=404, detail=f"Produto com SKU '{sku}' não encontrado")
    
    # Buscar histórico de preços
    precos = list(
        session.exec(
            select(PrecosHistoricos)
            .where(PrecosHistoricos.produto_id == produto.id)
            .order_by(PrecosHistoricos.coletado_em.desc())
            .limit(limit)
        )
    )
    
    # Reverter ordem para cronológica
    precos.reverse()
    
    return [
        {
            "date": preco.coletado_em.isoformat(),
            "coletado_em": preco.coletado_em.isoformat(),
            "preco": float(preco.preco),
            "price": float(preco.preco),
        }
        for preco in precos
    ]
