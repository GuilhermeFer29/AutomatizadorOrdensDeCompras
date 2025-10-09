from typing import Optional
from sqlmodel import Session, select
from app.models.models import Produto

def get_products(session: Session, search_term: Optional[str] = None):
    statement = select(Produto)
    if search_term:
        statement = statement.where(Produto.nome.contains(search_term) | Produto.sku.contains(search_term))
    return session.exec(statement).all()

def get_product_by_id(session: Session, product_id: int):
    return session.get(Produto, product_id)

def create_product(session: Session, product_data: dict):
    # Mock supplier and price for now
    new_product = Produto(
        sku=product_data['sku'],
        name=product_data['name'],
        supplier="Fornecedor Padrão",
        price=product_data.get('price', 0),
        stock=product_data.get('stock', 0)
    )
    session.add(new_product)
    session.commit()
    session.refresh(new_product)
    return new_product

def update_product(session: Session, product_id: int, product_data: dict):
    product = session.get(Produto, product_id)
    if not product:
        return None
    for key, value in product_data.items():
        setattr(product, key, value)
    session.add(product)
    session.commit()
    session.refresh(product)
    return product
