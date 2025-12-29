"""
Módulo de Previsão Simplificado (Project Lite)
Utiliza StatsForecast e AutoARIMA para previsões robustas e rápidas sem necessidade de GPU.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Any

import pandas as pd
import numpy as np
from statsforecast import StatsForecast
from statsforecast.models import AutoARIMA, Naive
from sqlmodel import Session, select

from app.core.database import engine
from app.models.models import PrecosHistoricos, Produto, VendasHistoricas

LOGGER = logging.getLogger(__name__)


# Configurações
MINIMUM_HISTORY_DAYS = 14  # Reduzido para permitir previsão com menos dados
DEFAULT_FORECAST_HORIZON = 14

class InsufficientHistoryError(Exception):
    """Erro levantado quando não há histórico suficiente para previsão."""
    pass

def _load_history_as_dataframe(
    session: Session,
    sku: str,
    days: int = 90
) -> pd.DataFrame:
    """Carrega histórico de PREÇOS e retorna DataFrame compatível com StatsForecast (unique_id, ds, y)."""
    
    # 1. Buscar produto
    produto = session.exec(select(Produto).where(Produto.sku == sku)).first()
    if not produto:
        raise ValueError(f"Produto {sku} não encontrado")

    # 2. Buscar histórico de PREÇOS (não vendas!)
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
    precos = list(session.exec(
        select(PrecosHistoricos)
        .where(PrecosHistoricos.produto_id == produto.id)
        .where(PrecosHistoricos.coletado_em >= cutoff_date)
        .order_by(PrecosHistoricos.coletado_em)
    ))

    if not precos:
        # Retorna DataFrame vazio se não houver preços
        return pd.DataFrame(columns=["unique_id", "ds", "y"])

    # 3. Converter para DataFrame
    df = pd.DataFrame([
        {
            "unique_id": sku,
            "ds": p.coletado_em,
            "y": float(p.preco)  # Usar PREÇO, não quantidade!
        } 
        for p in precos
    ])
    
    # 4. Agrupar por data (média dos preços do dia) e preencher gaps
    df["ds"] = pd.to_datetime(df["ds"]).dt.tz_localize(None)
    df = df.groupby(["unique_id", "ds"]).mean().reset_index()
    
    # Preencher dias faltantes com forward fill (manter último preço conhecido)
    if len(df) > 0:
        all_dates = pd.date_range(start=df["ds"].min(), end=df["ds"].max(), freq="D")
        df = (
            df.set_index("ds")
            .reindex(all_dates)
            .ffill()  # Forward fill para preços (não usar 0!)
            .rename_axis("ds")
            .reset_index()
        )
        df["unique_id"] = sku  # Restaurar ID após reindex
    
    return df

def predict_prices_for_product(
    sku: str,
    days_ahead: int = DEFAULT_FORECAST_HORIZON,
    target: str = "quantidade",  # Mantido para compatibilidade, mas foco é demanda
) -> Dict[str, Any]:
    """
    Gera previsão de demanda usando StatsForecast (AutoARIMA).
    """
    LOGGER.info(f"🔮 Iniciando previsão Lite para {sku} ({days_ahead} dias)")
    
    with Session(engine) as session:
        try:
            # 1. Carregar dados
            df = _load_history_as_dataframe(session, sku)
            
            # Validação
            if len(df) < MINIMUM_HISTORY_DAYS:
                LOGGER.warning(f"Histórico insuficiente para {sku}: {len(df)} dias (mínimo {MINIMUM_HISTORY_DAYS})")
                return _fallback_forecast(sku, days_ahead, "insufficient_history")

            # 2. Instanciar StatsForecast
            # AutoARIMA é robusto e não precisa de ajuste manual de hiperparâmetros
            # Naive é usado como baseline fallback se ARIMA falhar
            models = [
                AutoARIMA(season_length=7), 
                Naive()
            ]
            
            sf = StatsForecast(
                models=models,
                freq='D',
                n_jobs=1,  # Serial é seguro e rápido suficiente para 1 série
                verbose=False
            )

            # 3. Gerar previsão e métricas
            # Para popular o dashboard, precisamos de métricas de erro.
            # Vamos fazer um backtest rápido nos últimos 7 dias para estimar a acurácia.
            metrics = {
                "history_len": len(df),
                "mape": 0.0,
                "rmse": 0.0,
                "mae": 0.0
            }
            
            try:
                if len(df) > MINIMUM_HISTORY_DAYS + 7:
                    # Cross-validation simples (últimos 7 dias)
                    cv_df = sf.cross_validation(
                        df=df,
                        h=7,
                        step_size=7,
                        n_windows=1
                    )
                    # Calcular métricas
                    model_col = "AutoARIMA" if "AutoARIMA" in cv_df.columns else "Naive"
                    y_true = cv_df["y"].values
                    y_pred = cv_df[model_col].values
                    
                    # Evitar divisão por zero no MAPE
                    mask = y_true != 0
                    if np.any(mask):
                        metrics["mape"] = float(np.mean(np.abs((y_true[mask] - y_pred[mask]) / y_true[mask])) * 100)
                    
                    metrics["rmse"] = float(np.sqrt(np.mean((y_true - y_pred)**2)))
                    metrics["mae"] = float(np.mean(np.abs(y_true - y_pred)))
            except Exception as e:
                LOGGER.warning(f"Erro ao calcular métricas para {sku}: {e}")

            # 4. Previsão final (Futuro)
            sf.fit(df)
            forecast_df = sf.predict(h=days_ahead)
            
            # 5. Processar resultados
            # Preferência: AutoARIMA > Naive
            model_name = "AutoARIMA"
            if "AutoARIMA" in forecast_df.columns:
                preds = forecast_df["AutoARIMA"].values
            else:
                preds = forecast_df["Naive"].values
                model_name = "Naive"
            
            # Evitar valores negativos
            preds = np.maximum(preds, 0)
            
            dates = forecast_df["ds"].dt.strftime("%Y-%m-%d").tolist()
            values = [round(float(v), 2) for v in preds]

            LOGGER.info(f"✅ Previsão Lite concluída: {model_name} (MAPE: {metrics['mape']:.1f}%)")

            return {
                "sku": sku,
                "dates": dates,
                "prices": values,  # Campo nomeado 'prices' por compatibilidade com frontend
                "model_used": f"StatsForecast_{model_name}",
                "method": "statistical",
                "metrics": metrics
            }

        except Exception as e:
            LOGGER.error(f"❌ Erro na previsão Lite para {sku}: {str(e)}", exc_info=True)
            return _fallback_forecast(sku, days_ahead, str(e))

def _fallback_forecast(sku: str, days: int, reason: str) -> Dict[str, Any]:
    """Retorna previsão zerada ou média simples em caso de erro."""
    dates = [
        (datetime.now() + timedelta(days=i)).strftime("%Y-%m-%d")
        for i in range(1, days + 1)
    ]
    
    return {
        "sku": sku,
        "dates": dates,
        "prices": [0.0] * days,
        "model_used": "fallback_zero",
        "error": reason
    }
