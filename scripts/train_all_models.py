import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlmodel import Session, select
from app.core.database import engine, wait_for_database
from app.models.models import Produto, PrecosHistoricos
from app.ml.training import train_model
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def train_all_products(min_records: int = 30) -> None:
    """Treina modelos Prophet para todos os produtos com dados suficientes."""
    wait_for_database(engine)
    
    with Session(engine) as session:
        produtos = session.exec(select(Produto)).all()
        logger.info(f"📦 Encontrados {len(produtos)} produtos")
        
        trained = 0
        skipped = 0
        failed = 0
        
        for produto in produtos:
            # Verificar se tem dados históricos suficientes
            precos_count = session.exec(
                select(PrecosHistoricos)
                .where(PrecosHistoricos.produto_id == produto.id)
                .where(PrecosHistoricos.is_synthetic == False)  # noqa: PLR2004
            ).all()
            
            if len(precos_count) < min_records:
                logger.warning(f"⚠️  Produto {produto.id} ({produto.nome}): apenas {len(precos_count)} registros (mínimo: {min_records})")
                skipped += 1
                continue
            
            try:
                logger.info(f"🔄 Treinando modelo para produto {produto.id} ({produto.nome})...")
                model_path = train_model(produto.id)
                logger.info(f"✅ Modelo salvo: {model_path}")
                trained += 1
            except Exception as e:
                logger.error(f"❌ Erro ao treinar produto {produto.id}: {e}")
                failed += 1
        
        logger.info(f"""
🎉 Treinamento concluído!
   ✅ Treinados: {trained}
   ⚠️  Pulados (dados insuficientes): {skipped}
   ❌ Falhas: {failed}
        """)


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Treina modelos Prophet para todos os produtos")
    parser.add_argument(
        "--min-records",
        type=int,
        default=30,
        help="Mínimo de registros históricos necessários (padrão: 30)"
    )
    
    args = parser.parse_args()
    train_all_products(args.min_records)
