"""
Service for scraping product prices from external sources.

NOTA: Em produção, este serviço se conectaria a APIs externas ou faria web scraping real.
Por ora, retorna o preço atual do produto do banco de dados como fallback.
"""


from sqlmodel import Session, select

from app.models.models import PrecosHistoricos, Produto


def scrape_and_save_price(product_id: int, session: Session = None) -> float | None:
    """
    Obtém o preço de um produto. Em produção, faria scraping externo.

    Atualmente retorna o preço do banco de dados como fallback.

    Args:
        product_id (int): O ID do produto.
        session (Session): Sessão do banco de dados (opcional).

    Returns:
        Optional[float]: O preço do produto, ou None se não encontrado.
    """
    if session:
        produto = session.get(Produto, product_id)
        if produto:
            latest_price = session.exec(
                select(PrecosHistoricos)
                .where(PrecosHistoricos.produto_id == produto.id)
                .order_by(PrecosHistoricos.coletado_em.desc())
            ).first()
            if latest_price:
                return float(latest_price.preco)

    # Fallback: se não tiver sessão ou produto, retorna None
    return None


def get_market_price_for_sku(sku: str, session: Session = None) -> float | None:
    """
    Busca preço de mercado para um SKU específico.

    Em produção, consultaria APIs de e-commerce ou faria web scraping.
    Atualmente retorna o preço atual do produto com pequena variação.

    Args:
        sku (str): O SKU do produto.
        session (Session): Sessão do banco de dados.

    Returns:
        Optional[float]: Preço de mercado estimado.
    """
    if session:
        produto = session.exec(select(Produto).where(Produto.sku == sku)).first()
        if produto:
            latest_price = session.exec(
                select(PrecosHistoricos)
                .where(PrecosHistoricos.produto_id == produto.id)
                .order_by(PrecosHistoricos.coletado_em.desc())
            ).first()
            if latest_price:
                # Simula variação de mercado de ±5%
                import random
                variation = random.uniform(0.95, 1.05)
                return round(float(latest_price.preco) * variation, 2)

    return None
