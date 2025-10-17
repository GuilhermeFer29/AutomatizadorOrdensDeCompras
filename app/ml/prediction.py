"""
Pipeline de previsão autorregressiva para modelos por produto.

ARQUITETURA:
============
✅ Previsão autorregressiva multi-step (usa previsões anteriores como input)
✅ Reconstrução automática de features temporais
✅ Suporte a janelas móveis dinâmicas
✅ Gestão de feriados e calendário
✅ Fallback para médias se modelo não disponível

COMO FUNCIONA:
==============
Para prever D+7:
1. D+1: Usa histórico real até D
2. D+2: Usa histórico real + previsão D+1
3. D+3: Usa histórico real + previsões D+1 e D+2
... e assim por diante

Isso captura a dependência temporal entre as previsões.
"""

from __future__ import annotations

from collections import deque
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Tuple

import holidays
import numpy as np
import pandas as pd
import structlog
from sqlmodel import Session, select

from app.core.database import engine
from app.ml.model_manager import ModelNotFoundError, load_model
from app.models.models import PrecosHistoricos, Produto, VendasHistoricas

LOGGER = structlog.get_logger(__name__)

# Configurações
MINIMUM_HISTORY_DAYS = 30  # Histórico mínimo necessário para previsão (reduzido de 60 para 30)
DEFAULT_FORECAST_HORIZON = 14  # Dias à frente por padrão

# Feriados brasileiros
BR_HOLIDAYS = holidays.Brazil()


class InsufficientHistoryError(Exception):
    """Exceção lançada quando não há histórico suficiente."""


def _load_recent_history(
    session: Session,
    sku: str,
    days: int = 60,
) -> Tuple[Produto, pd.DataFrame]:
    """
    Carrega histórico recente de preços e vendas.
    
    Args:
        session: Sessão do banco de dados
        sku: SKU do produto
        days: Número de dias de histórico a carregar
    
    Returns:
        Tupla (produto, dataframe)
    """
    # Buscar produto
    produto = session.exec(select(Produto).where(Produto.sku == sku)).first()
    if not produto:
        raise ValueError(f"Produto com SKU '{sku}' não encontrado")
    
    # Data limite (days atrás)
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
    
    # Carregar preços recentes
    precos = list(
        session.exec(
            select(PrecosHistoricos)
            .where(PrecosHistoricos.produto_id == produto.id)
            .where(PrecosHistoricos.coletado_em >= cutoff_date)
            .order_by(PrecosHistoricos.coletado_em)
        )
    )
    
    # Carregar vendas recentes
    vendas = list(
        session.exec(
            select(VendasHistoricas)
            .where(VendasHistoricas.produto_id == produto.id)
            .where(VendasHistoricas.data_venda >= cutoff_date)
            .order_by(VendasHistoricas.data_venda)
        )
    )
    
    if len(precos) < MINIMUM_HISTORY_DAYS:
        raise InsufficientHistoryError(
            f"Histórico insuficiente para {sku}. "
            f"Encontrado: {len(precos)} dias, mínimo: {MINIMUM_HISTORY_DAYS}"
        )
    
    # Criar DataFrame
    price_rows = []
    for preco in precos:
        date = preco.coletado_em
        if date.tzinfo is None:
            date = date.replace(tzinfo=timezone.utc)
        price_rows.append({
            "date": date.astimezone(timezone.utc).replace(tzinfo=None).date(),
            "price": float(preco.preco),
        })
    
    df_prices = pd.DataFrame(price_rows)
    df_prices = df_prices.groupby("date").agg({"price": "mean"}).reset_index()
    
    # Vendas
    sales_rows = []
    for venda in vendas:
        date = venda.data_venda
        if date.tzinfo is None:
            date = date.replace(tzinfo=timezone.utc)
        sales_rows.append({
            "date": date.astimezone(timezone.utc).replace(tzinfo=None).date(),
            "quantity": venda.quantidade,
        })
    
    df_sales = pd.DataFrame(sales_rows) if sales_rows else pd.DataFrame(columns=["date", "quantity"])
    if not df_sales.empty:
        df_sales = df_sales.groupby("date").agg({"quantity": "sum"}).reset_index()
    
    # Merge
    df = df_prices.copy()
    if not df_sales.empty:
        df = df.merge(df_sales, on="date", how="left")
        df["quantity"] = df["quantity"].fillna(0)
    else:
        df["quantity"] = 0
    
    df = df.sort_values("date").reset_index(drop=True)
    
    return produto, df


def _build_features_for_date(
    target_date: datetime.date,
    price_history: deque,
    quantity_history: deque,
) -> Dict[str, float]:
    """
    Constrói features para uma data futura usando histórico.
    
    Args:
        target_date: Data para qual construir features
        price_history: Deque com histórico de preços
        quantity_history: Deque com histórico de quantidades
    
    Returns:
        Dicionário com features
    """
    features = {}
    
    target_dt = datetime.combine(target_date, datetime.min.time())
    
    # ==========================
    # 1. FEATURES DE CALENDÁRIO
    # ==========================
    features["day_of_week"] = target_dt.weekday()
    features["day_of_month"] = target_dt.day
    features["week_of_year"] = target_dt.isocalendar().week
    features["month"] = target_dt.month
    features["quarter"] = (target_dt.month - 1) // 3 + 1
    features["is_weekend"] = 1 if target_dt.weekday() >= 5 else 0
    features["is_month_start"] = 1 if target_dt.day == 1 else 0
    features["is_month_end"] = 1 if target_dt.day >= 28 else 0  # Aproximação
    
    # ==========================
    # 2. FEATURES DE FERIADOS
    # ==========================
    features["is_holiday"] = 1 if target_date in BR_HOLIDAYS else 0
    
    # Dias até próximo feriado
    days_to_holiday = 30
    for i in range(1, 31):
        future_date = target_date + timedelta(days=i)
        if future_date in BR_HOLIDAYS:
            days_to_holiday = i
            break
    features["days_to_holiday"] = days_to_holiday
    
    # Dias desde último feriado
    days_from_holiday = 30
    for i in range(1, 31):
        past_date = target_date - timedelta(days=i)
        if past_date in BR_HOLIDAYS:
            days_from_holiday = i
            break
    features["days_from_holiday"] = days_from_holiday
    
    # ==========================
    # 3. FEATURES DE LAG
    # ==========================
    price_list = list(price_history)
    quantity_list = list(quantity_history)
    
    def safe_lag(lst, lag):
        return lst[-lag] if len(lst) >= lag else lst[-1] if lst else 0.0
    
    for lag in [1, 2, 7, 14, 30]:
        features[f"price_lag_{lag}"] = safe_lag(price_list, lag)
        features[f"quantity_lag_{lag}"] = safe_lag(quantity_list, lag)
    
    # ==========================
    # 4. FEATURES DE ROLLING
    # ==========================
    for window in [7, 14, 30]:
        # Preço
        window_prices = price_list[-window:] if len(price_list) >= window else price_list
        if window_prices:
            features[f"price_rolling_mean_{window}"] = np.mean(window_prices)
            features[f"price_rolling_std_{window}"] = np.std(window_prices)
            features[f"price_rolling_min_{window}"] = np.min(window_prices)
            features[f"price_rolling_max_{window}"] = np.max(window_prices)
        else:
            features[f"price_rolling_mean_{window}"] = 0.0
            features[f"price_rolling_std_{window}"] = 0.0
            features[f"price_rolling_min_{window}"] = 0.0
            features[f"price_rolling_max_{window}"] = 0.0
        
        # Quantidade
        window_quantities = quantity_list[-window:] if len(quantity_list) >= window else quantity_list
        if window_quantities:
            features[f"quantity_rolling_mean_{window}"] = np.mean(window_quantities)
            features[f"quantity_rolling_std_{window}"] = np.std(window_quantities)
            features[f"quantity_rolling_sum_{window}"] = np.sum(window_quantities)
        else:
            features[f"quantity_rolling_mean_{window}"] = 0.0
            features[f"quantity_rolling_std_{window}"] = 0.0
            features[f"quantity_rolling_sum_{window}"] = 0.0
    
    # ==========================
    # 5. FEATURES DERIVADAS
    # ==========================
    price_ma7 = features["price_rolling_mean_7"]
    price_ma30 = features["price_rolling_mean_30"]
    
    features["price_vs_ma7"] = safe_lag(price_list, 1) / (price_ma7 + 1e-6)
    features["price_vs_ma30"] = safe_lag(price_list, 1) / (price_ma30 + 1e-6)
    features["price_volatility_7"] = features["price_rolling_std_7"] / (price_ma7 + 1e-6)
    
    return features


def predict_prices_for_product(
    sku: str,
    days_ahead: int = DEFAULT_FORECAST_HORIZON,
) -> Dict[str, List]:
    """
    Gera previsões autorregressivas para um produto.
    
    Args:
        sku: SKU do produto
        days_ahead: Número de dias à frente para prever
    
    Returns:
        Dicionário com:
        - dates: Lista de datas das previsões
        - prices: Lista de preços previstos
        - model_used: Nome do modelo usado
    """
    LOGGER.info(f"Iniciando previsão para {sku}: {days_ahead} dias à frente")
    
    try:
        # Carregar modelo
        model, scaler, metadata = load_model(sku)
        LOGGER.info(f"Modelo carregado: {metadata.model_type} v{metadata.version}")
        
    except ModelNotFoundError:
        LOGGER.warning(f"Modelo não encontrado para {sku}, usando fallback")
        return _fallback_prediction(sku, days_ahead)
    
    with Session(engine) as session:
        # Carregar histórico recente (60 dias para features de lag/rolling adequadas)
        produto, df_history = _load_recent_history(session, sku, days=60)
        
        # Inicializar deques com histórico
        price_history = deque(df_history["price"].tolist(), maxlen=60)
        quantity_history = deque(df_history["quantity"].tolist(), maxlen=60)
        
        # Data inicial para previsão (dia seguinte ao último histórico)
        last_date = df_history["date"].max()
        if isinstance(last_date, pd.Timestamp):
            last_date = last_date.date()
        
        # Gerar previsões autorregressivas
        forecast_dates = []
        forecast_prices = []
        
        for step in range(1, days_ahead + 1):
            # Data alvo
            target_date = last_date + timedelta(days=step)
            
            # Construir features
            features_dict = _build_features_for_date(
                target_date=target_date,
                price_history=price_history,
                quantity_history=quantity_history,
            )
            
            # Ordenar features conforme esperado pelo modelo
            feature_values = [features_dict[col] for col in metadata.features]
            feature_array = np.array(feature_values).reshape(1, -1)
            
            # 🔧 CORREÇÃO CRÍTICA: Normalizar features com o scaler treinado
            feature_array_scaled = scaler.transform(feature_array)
            
            # 🔍 DEBUG: Log das features (apenas primeiros 5 passos)
            if step <= 5:
                LOGGER.debug(
                    f"Step D+{step}",
                    date=target_date.isoformat(),
                    price_lag_1=features_dict.get('price_lag_1', 0.0),
                    price_lag_7=features_dict.get('price_lag_7', 0.0),
                    price_rolling_mean_7=features_dict.get('price_rolling_mean_7', 0.0),
                    last_3_prices=list(price_history)[-3:]
                )
            
            # Prever usando features normalizadas
            predicted_price = model.predict(feature_array_scaled)[0]
            predicted_price = max(predicted_price, 0.0)  # Garantir não-negativo
            
            # Adicionar aos resultados
            forecast_dates.append(target_date.isoformat())
            forecast_prices.append(round(float(predicted_price), 2))
            
            # 🔄 ATUALIZAÇÃO AUTORREGRESSIVA: Usar previsão como input para próximo passo
            price_history.append(predicted_price)
            
            # Quantidade: usar média recente como estimativa
            avg_quantity = np.mean(list(quantity_history)[-7:])
            quantity_history.append(avg_quantity)
        
        LOGGER.info(f"✅ Previsão concluída para {sku}: {len(forecast_prices)} dias")
        
        return {
            "sku": sku,
            "dates": forecast_dates,
            "prices": forecast_prices,
            "model_used": f"{metadata.model_type}_v{metadata.version}",
            "metrics": metadata.metrics,
        }


def _fallback_prediction(sku: str, days_ahead: int) -> Dict[str, List]:
    """
    Previsão fallback usando média móvel quando modelo não disponível.
    """
    LOGGER.warning(f"Usando previsão fallback (média móvel) para {sku}")
    
    with Session(engine) as session:
        try:
            produto, df_history = _load_recent_history(session, sku, days=30)
        except (ValueError, InsufficientHistoryError) as e:
            LOGGER.error(f"Não foi possível gerar previsão fallback: {e}")
            return {
                "sku": sku,
                "dates": [],
                "prices": [],
                "model_used": "none",
                "error": str(e),
            }
        
        # Usar média dos últimos 14 dias
        avg_price = df_history["price"].tail(14).mean()
        last_date = df_history["date"].max()
        if isinstance(last_date, pd.Timestamp):
            last_date = last_date.date()
        
        forecast_dates = [
            (last_date + timedelta(days=i)).isoformat()
            for i in range(1, days_ahead + 1)
        ]
        forecast_prices = [round(float(avg_price), 2)] * days_ahead
        
        return {
            "sku": sku,
            "dates": forecast_dates,
            "prices": forecast_prices,
            "model_used": "moving_average_fallback",
            "metrics": {},
        }


__all__ = [
    "predict_prices_for_product",
    "InsufficientHistoryError",
]
