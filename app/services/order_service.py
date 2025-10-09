from typing import Optional
from sqlmodel import Session, select
from app.models.models import OrdemDeCompra, Produto
from app.services.task_service import trigger_retrain_global_model_task

def get_orders(session: Session, status: Optional[str] = None, search: Optional[str] = None):
    statement = select(OrdemDeCompra).join(Produto)
    if status and status != 'all':
        statement = statement.where(OrdemDeCompra.status == status)
    if search:
        statement = statement.where(Produto.nome.contains(search) | OrdemDeCompra.id.contains(search))
    return session.exec(statement).all()

def create_order(session: Session, order_data: dict):
    # Simple logic to find a product to associate with the order
    product = session.exec(select(Produto).where(Produto.nome == order_data['product'])).first()
    if not product:
        # Create a mock product if it doesn't exist
        product = Produto(nome=order_data['product'], sku=f"SKU_{order_data['product']}", estoque_atual=100, estoque_minimo=20)
        session.add(product)
        session.flush()

    new_order = OrdemDeCompra(
        produto_id=product.id,
        quantity=order_data['quantity'],
        value=order_data['value'],
        status='pending',
        origin=order_data.get('origin', 'Manual')
    )
    session.add(new_order)
    session.commit()
    session.refresh(new_order)

    # Dispara o retreinamento do modelo em segundo plano
    trigger_retrain_global_model_task.delay()

    return new_order
