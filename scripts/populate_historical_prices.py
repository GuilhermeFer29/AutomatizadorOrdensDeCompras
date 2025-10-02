import sys
from pathlib import Path
from datetime import datetime, timedelta
from random import uniform, randint

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlmodel import Session, select
from app.core.database import engine, wait_for_database
from app.models.models import Produto, PrecosHistoricos
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def generate_historical_prices(produto_id: int, days: int = 90, base_price: float = 100.0) -> None:
    """Gera preços históricos simulados para um produto."""
    with Session(engine) as session:
        produto = session.get(Produto, produto_id)
        if not produto:
            logger.error(f"❌ Produto {produto_id} não encontrado")
            return
        
        # Verificar se já tem dados históricos
        existing_count = session.exec(
            select(PrecosHistoricos).where(PrecosHistoricos.produto_id == produto_id)
        ).all()
        
        if len(existing_count) >= 30:
            logger.info(f"⚠️  Produto {produto_id} ({produto.nome}) já tem {len(existing_count)} preços históricos")
            return
        
        # Gerar preços históricos com tendência e sazonalidade
        end_date = datetime.utcnow()
        created = 0
        
        for i in range(days):
            data_referencia = end_date - timedelta(days=days - i)
            
            # Simular variação de preço: tendência + ruído + sazonalidade semanal
            trend = 0.0005 * i  # Leve tendência de alta
            seasonality = 0.05 * (1 if data_referencia.weekday() < 5 else -1)  # Mais caro em dias úteis
            noise = uniform(-0.03, 0.03)
            
            preco = base_price * (1 + trend + seasonality + noise)
            
            # Criar registro
            preco_hist = PrecosHistoricos(
                produto_id=produto_id,
                preco=round(preco, 2),
                data_coleta=data_referencia,
                fonte="scraping_simulado"
            )
            session.add(preco_hist)
            created += 1
        
        session.commit()
        logger.info(f"✅ Produto {produto_id} ({produto.nome}): {created} preços históricos criados")


def populate_all_products(days: int = 90) -> None:
    """Popula preços históricos para todos os produtos."""
    wait_for_database(engine)
    
    with Session(engine) as session:
        produtos = session.exec(select(Produto)).all()
        logger.info(f"📦 Encontrados {len(produtos)} produtos para popular")
        
        for produto in produtos:
            # Preço base varia por categoria
            if "Espuma" in produto.categoria or "Tecido" in produto.categoria:
                base_price = uniform(80, 200)
            elif "Madeira" in produto.categoria:
                base_price = uniform(50, 150)
            elif "Fixador" in produto.categoria or "Acabamento" in produto.categoria:
                base_price = uniform(20, 100)
            else:
                base_price = uniform(50, 120)
            
            generate_historical_prices(produto.id, days, base_price)
    
    logger.info("🎉 Populagem de preços históricos concluída!")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Popula preços históricos simulados")
    parser.add_argument(
        "--days",
        type=int,
        default=90,
        help="Quantidade de dias de histórico (padrão: 90)"
    )
    parser.add_argument(
        "--produto-id",
        type=int,
        default=None,
        help="ID de produto específico (opcional, se omitido processa todos)"
    )
    
    args = parser.parse_args()
    
    if args.produto_id:
        generate_historical_prices(args.produto_id, args.days)
    else:
        populate_all_products(args.days)
