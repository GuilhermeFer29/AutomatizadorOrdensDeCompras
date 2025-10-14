from typing import List, Optional
import logging
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlmodel import Session
from app.core.database import get_session
from app.services.product_service import get_products, get_product_by_id, create_product, update_product
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
    return get_products(session, search)


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
