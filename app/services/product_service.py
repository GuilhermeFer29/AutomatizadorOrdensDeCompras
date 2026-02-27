
from datetime import datetime, timezone

from sqlmodel import Session, select

from app.models.models import PrecosHistoricos, Produto


def get_products(session: Session, search_term: str | None = None):
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
    session.flush()  # Gera o ID sem finalizar a transação

    # Se preço foi fornecido, cria registro no historico de precos
    price = product_data.get('price')
    if price is not None and price > 0:
        preco_hist = PrecosHistoricos(
            produto_id=new_product.id,
            preco=price,
            moeda="BRL",
            fornecedor="Cadastro inicial",
            coletado_em=datetime.now(timezone.utc),
            tenant_id=new_product.tenant_id,
        )
        session.add(preco_hist)

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
    }

    for key, value in product_data.items():
        if key == 'price':
            continue  # price is handled separately below
        model_field = field_mapping.get(key, key)  # Use mapping or original key
        if hasattr(product, model_field):
            setattr(product, model_field, value)

    product.atualizado_em = datetime.now(timezone.utc)

    # Se preço foi informado, cria novo registro historico
    price = product_data.get('price')
    if price is not None and price > 0:
        preco_hist = PrecosHistoricos(
            produto_id=product.id,
            preco=price,
            moeda="BRL",
            fornecedor="Atualização manual",
            coletado_em=datetime.now(timezone.utc),
            tenant_id=product.tenant_id,
        )
        session.add(preco_hist)

    session.add(product)
    session.commit()
    session.refresh(product)
    return product
