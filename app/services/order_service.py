from typing import Optional
from sqlmodel import Session, select
from app.models.models import OrdemDeCompra, Produto, Fornecedor

def get_orders(session: Session, status: Optional[str] = None, search: Optional[str] = None):
    statement = select(OrdemDeCompra).join(Produto)
    if status and status != 'all':
        statement = statement.where(OrdemDeCompra.status == status)
    if search:
        statement = statement.where(Produto.nome.contains(search) | OrdemDeCompra.id.contains(search))
    return session.exec(statement).all()

def get_or_create_default_fornecedor(session: Session) -> Fornecedor:
    """Get or create a default supplier for orders."""
    fornecedor = session.exec(
        select(Fornecedor).where(Fornecedor.nome == "Fornecedor Padrão")
    ).first()
    
    if not fornecedor:
        fornecedor = Fornecedor(
            nome="Fornecedor Padrão",
            confiabilidade=0.9,
            prazo_entrega_dias=7
        )
        session.add(fornecedor)
        session.flush()
    
    return fornecedor

def create_order(session: Session, order_data: dict):
    # Find or create product
    product = session.exec(select(Produto).where(Produto.nome == order_data['product'])).first()
    if not product:
        product = Produto(nome=order_data['product'], sku=f"SKU_{order_data['product']}", estoque_atual=100, estoque_minimo=20)
        session.add(product)
        session.flush()

    # Get or create default supplier
    fornecedor = get_or_create_default_fornecedor(session)

    new_order = OrdemDeCompra(
        produto_id=product.id,
        fornecedor_id=fornecedor.id,  # Now properly set
        quantidade=order_data['quantity'],
        valor=order_data['value'],
        status='pending',
        origem=order_data.get('origin', 'Manual')
    )
    session.add(new_order)
    session.commit()
    session.refresh(new_order)

    return new_order

