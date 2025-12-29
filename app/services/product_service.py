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
    # Map English API fields to Portuguese model fields
    new_product = Produto(
        sku=product_data['sku'],
        nome=product_data['name'],  # API: name -> Model: nome
        categoria=product_data.get('categoria'),
        estoque_atual=product_data.get('stock', 0),  # API: stock -> Model: estoque_atual
        estoque_minimo=product_data.get('estoque_minimo', 10),  # Default minimum stock
    )
    session.add(new_product)
    session.commit()
    session.refresh(new_product)
    return new_product

def update_product(session: Session, product_id: int, product_data: dict):
    product = session.get(Produto, product_id)
    if not product:
        return None
    
    # Map English API fields to Portuguese model fields
    field_mapping = {
        'name': 'nome',
        'stock': 'estoque_atual',
        'price': 'preco_medio',  # If price update needed
    }
    
    for key, value in product_data.items():
        model_field = field_mapping.get(key, key)  # Use mapping or original key
        if hasattr(product, model_field):
            setattr(product, model_field, value)
    
    session.add(product)
    session.commit()
    session.refresh(product)
    return product
