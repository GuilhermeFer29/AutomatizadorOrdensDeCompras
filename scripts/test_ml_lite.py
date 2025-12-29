"""
Script de Validação ML Lite
Verifica se o StatsForecast está gerando previsões corretamente a partir do banco de dados.
"""
import logging
import sys
from datetime import datetime, timedelta
from decimal import Decimal

# Adiciona diretório raiz ao path
import os
sys.path.append(os.getcwd())

from sqlmodel import Session, select, delete
from app.core.database import engine
from app.models.models import Produto, VendasHistoricas
from app.ml.prediction import predict_prices_for_product

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("validation")

def seed_test_data(session: Session, sku: str):
    """Cria dados de venda sintéticos para teste."""
    # 1. Limpar dados anteriores
    produto = session.exec(select(Produto).where(Produto.sku == sku)).first()
    if produto:
        session.exec(delete(VendasHistoricas).where(VendasHistoricas.produto_id == produto.id))
        session.delete(produto)
        session.commit()

    # 2. Criar Produto
    produto = Produto(
        sku=sku,
        nome=f"Produto Teste {sku}",
        categoria="Teste",
        estoque_atual=100,
        estoque_minimo=10,
        custo_unitario=Decimal("10.00")
    )
    session.add(produto)
    session.commit()
    session.refresh(produto)

    # 3. Criar histórico de vendas (padrão sazonal simples)
    vendas = []
    base_date = datetime.now() - timedelta(days=60)
    for i in range(60):
        date = base_date + timedelta(days=i)
        # Padrão: 10 + senoide + ruido
        qty = 10 + (i % 7) # Sazonalidade semanal
        
        vendas.append(VendasHistoricas(
            produto_id=produto.id,
            data_venda=date,
            quantidade=qty,
            receita=Decimal(qty * 20.00)
        ))
    
    session.add_all(vendas)
    session.commit()
    logger.info(f"✅ Dados de teste criados para {sku}")

def validate_prediction(sku: str):
    """Executa previsão e valida retorno."""
    try:
        resultado = predict_prices_for_product(sku, days_ahead=7)
        
        # Validações
        if not resultado:
            logger.error("❌ Resultado vazio")
            return False
            
        if resultado.get("error"):
            logger.error(f"❌ Erro retornado: {resultado['error']}")
            return False
            
        dates = resultado.get("dates", [])
        values = resultado.get("prices", [])
        
        if len(dates) != 7 or len(values) != 7:
            logger.error(f"❌ Tamanho incorreto: {len(dates)} datas, {len(values)} valores")
            return False
            
        logger.info(f"✅ Previsão Sucesso! Modelo: {resultado['model_used']}")
        logger.info(f"   Previsões: {values}")
        return True
        
    except Exception as e:
        logger.error(f"❌ Exceção na previsão: {e}")
        return False

if __name__ == "__main__":
    SKU_TESTE = "TEST-LITE-001"
    
    with Session(engine) as session:
        seed_test_data(session, SKU_TESTE)
    
    success = validate_prediction(SKU_TESTE)
    
    if success:
        print("\n🎉 VALIDAÇÃO ML LITE CONCLUÍDA COM SUCESSO!")
        sys.exit(0)
    else:
        print("\n💥 FALHA NA VALIDAÇÃO ML LITE")
        sys.exit(1)
