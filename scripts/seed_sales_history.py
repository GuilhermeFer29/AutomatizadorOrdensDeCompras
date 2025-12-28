
import sys
import random
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

from sqlmodel import Session, select
from sqlalchemy import text

# Setup paths
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.core.database import engine
from app.models.models import Produto, VendasHistoricas

def seed_sales_limit(days=60):
    print(f"🌱 Gerando {days} dias de histórico de vendas para produtos...")
    
    with Session(engine) as session:
        # Obter todos os produtos
        products = session.exec(select(Produto)).all()
        
        if not products:
            print("❌ Nenhum produto encontrado. Rode seed_database.py primeiro.")
            return

        total_records = 0
        
        for produto in products:
            print(f"   > Processando: {produto.nome} ({produto.sku})")
            
            # Verificar data da última venda pra não duplicar demais
            last_sale = session.exec(
                select(VendasHistoricas)
                .where(VendasHistoricas.produto_id == produto.id)
                .order_by(VendasHistoricas.data_venda.desc())
            ).first()
            
            start_date = datetime.now(timezone.utc) - timedelta(days=days)
            if last_sale:
                 # Se já tem venda recente, não faz nada ou complementa? 
                 # Vamos assumir que se tem menos de 14 dias, completa.
                 # Para simplificar: apaga tudo desse produto ou só adiciona se vazio?
                 # Melhor: Adiciona apenas se não tiver nada nos últimos 15 dias.
                 if (datetime.now(timezone.utc) - last_sale.data_venda).days < 5:
                     print(f"     ⚠️ Já possui dados recentes. Pulando.")
                     continue

            # Gera vendas diárias
            current_date = start_date
            records = []
            while current_date < datetime.now(timezone.utc):
                # Randomize sales volume based on stock info roughly
                # Base de 0 a 20 unidades por dia
                qtd = random.randint(0, 20)
                
                # Preço base (simulado, já que PriceHistory pode estar vazio)
                preco_unitario = Decimal(random.uniform(10.0, 100.0))
                
                venda = VendasHistoricas(
                    produto_id=produto.id,
                    data_venda=current_date,
                    quantidade=qtd,
                    receita=preco_unitario * qtd
                )
                session.add(venda)
                records.append(venda)
                
                current_date += timedelta(days=1)
            
            total_records += len(records)
        
        session.commit()
        print(f"✅ Sucesso! {total_records} registros de vendas criados.")

if __name__ == "__main__":
    seed_sales_limit()
