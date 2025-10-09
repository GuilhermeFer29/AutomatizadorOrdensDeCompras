from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session
from app.core.database import get_session
from app.services.product_service import get_products, get_product_by_id, create_product, update_product
from pydantic import BaseModel

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
def handle_create_product(product: ProductCreate, session: Session = Depends(get_session)):
    return create_product(session, product.dict())

@router.put("/{product_id}")
def handle_update_product(product_id: int, product: ProductUpdate, session: Session = Depends(get_session)):
    updated_product = update_product(session, product_id, product.dict(exclude_unset=True))
    if not updated_product:
        raise HTTPException(status_code=404, detail="Product not found")
    return updated_product
