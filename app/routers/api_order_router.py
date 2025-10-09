from typing import Optional
from fastapi import APIRouter, Depends
from sqlmodel import Session
from app.core.database import get_session
from app.services.order_service import get_orders, create_order
from pydantic import BaseModel

class OrderCreate(BaseModel):
    product: str
    quantity: int
    value: float
    origin: Optional[str] = 'Manual'

router = APIRouter(prefix="/api/orders", tags=["api-orders"])

@router.get("/")
def read_orders(status: Optional[str] = None, search: Optional[str] = None, session: Session = Depends(get_session)):
    return get_orders(session, status, search)

@router.post("/")
def handle_create_order(order: OrderCreate, session: Session = Depends(get_session)):
    return create_order(session, order.dict())
