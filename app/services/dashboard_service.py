import json
from pathlib import Path
from sqlmodel import Session, select, func
from app.models.models import OrdemDeCompra, Produto
from app.core.config import ROOT_DIR

def get_dashboard_kpis(session: Session):
    # Carrega métricas do modelo de ML, se existirem
    model_accuracy = 0.0
    metadata_path = ROOT_DIR / "models" / "global_lgbm_metadata.json"
    if metadata_path.exists():
        with open(metadata_path, 'r') as f:
            metadata = json.load(f)
            # Usando RMSE como a métrica de acurácia
            model_accuracy = metadata.get("metrics", {}).get("rmse", 0.0)

    # O cálculo de "economia" real é complexo e depende da lógica de negócio.
    # Por enquanto, retornaremos 0.
    total_economy = 0.0
    
    automated_orders = session.exec(
        select(func.count(OrdemDeCompra.id)).where(OrdemDeCompra.origem == "Automática")
    ).one_or_none() or 0

    # Lógica simples para o nível de estoque
    total_products = session.exec(select(func.count(Produto.id))).one_or_none() or 1
    low_stock_count = session.exec(
        select(func.count(Produto.id)).where(Produto.estoque_atual < Produto.estoque_minimo)
    ).one_or_none() or 0
    stock_level = "Crítico" if (low_stock_count / total_products) > 0.5 else "Saudável"

    return {
        "economy": total_economy,
        "automatedOrders": automated_orders,
        "stockLevel": stock_level,
        "modelAccuracy": model_accuracy,
    }

def get_dashboard_alerts(session: Session):
    low_stock_products = session.exec(
        select(Produto).where(Produto.estoque_atual < Produto.estoque_minimo)
    ).all()
    
    alerts = []
    for product in low_stock_products:
        alerts.append({
            "id": product.id,
            "product": product.nome,
            "alert": "Estoque baixo",
            "stock": product.estoque_atual,
            "severity": "error",
        })
    

    return alerts
