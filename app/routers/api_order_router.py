from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlmodel import Session, select
from app.core.database import get_session
from app.services.order_service import get_orders, create_order
from app.models.models import OrdemDeCompra
from pydantic import BaseModel, Field
from app.core.cache import cache_response, invalidate_dashboard_cache

class OrderCreate(BaseModel):
    product: str = Field(..., min_length=1, max_length=255, description="Nome do produto")
    quantity: int = Field(gt=0, description="A quantidade deve ser maior que zero")
    value: float = Field(gt=0, description="O valor deve ser positivo")
    origin: Optional[str] = Field(default='Manual', max_length=100, description="Origem da ordem")

class OrderRead(BaseModel):
    id: int
    product: str
    quantity: int
    value: float
    status: str
    origin: str
    date: str
    supplier: Optional[str] = None
    justification: Optional[str] = None

router = APIRouter(prefix="/api/orders", tags=["api-orders"])

@router.get("/", response_model=list[OrderRead])
@cache_response(namespace="orders")
def read_orders(status: Optional[str] = None, search: Optional[str] = None, session: Session = Depends(get_session)):
    orders = get_orders(session, status, search)
    # Map models to schema manually to handle product name and date formatting
    return [
        OrderRead(
            id=o.id,
            product=o.produto.nome if o.produto else "Desconhecido",
            quantity=o.quantidade,
            value=float(o.valor),
            status=o.status,
            origin=o.origem,
            date=o.data_criacao.isoformat(),
            supplier=o.fornecedor.nome if o.fornecedor else "Padrão",
            justification=o.justificativa
        ) for o in orders
    ]

@router.post("/")
async def handle_create_order(
    order: OrderCreate, 
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session)
):
    result = create_order(session, order.model_dump())
    # Invalida cache do dashboard em background
    background_tasks.add_task(invalidate_dashboard_cache)
    return result

@router.post("/{order_id}/approve", tags=["api-orders"])
async def approve_order(
    order_id: int, 
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session)
):
    """Aprova uma ordem de compra pendente."""
    order = session.get(OrdemDeCompra, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Ordem não encontrada")
    if order.status != "pending":
        raise HTTPException(status_code=400, detail="Apenas ordens pendentes podem ser aprovadas")
    order.status = "approved"
    session.add(order)
    session.commit()
    session.refresh(order)
    
    # Invalida cache do dashboard em background
    background_tasks.add_task(invalidate_dashboard_cache)
    
    return order

@router.post("/{order_id}/reject", tags=["api-orders"])
async def reject_order(
    order_id: int, 
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session)
):
    """Rejeita uma ordem de compra pendente."""
    order = session.get(OrdemDeCompra, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Ordem não encontrada")
    if order.status != "pending":
        raise HTTPException(status_code=400, detail="Apenas ordens pendentes podem ser rejeitadas")
    order.status = "cancelled"
    session.add(order)
    session.commit()
    session.refresh(order)
    
    # Invalida cache do dashboard em background
    background_tasks.add_task(invalidate_dashboard_cache)
    
    return order
