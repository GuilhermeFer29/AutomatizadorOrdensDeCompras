"""
Pipeline de treinamento de modelos ML por produto com feature engineering avançado.

ARQUITETURA NOVA (2025-10-16):
===============================
✅ Modelos especializados por produto (não mais global)
✅ Feature engineering de alta qualidade (calendário, lag, rolling, feriados)
✅ Validação cruzada com TimeSeriesSplit
✅ Otimização de hiperparâmetros com Optuna
✅ Modelo LightGBM otimizado para séries temporais
✅ Gestão granular via model_manager.py

MELHORES PRÁTICAS:
==================
- Features de calendário: dia semana, mês, trimestre, feriados
- Features de lag: D-1, D-2, D-7, D-14, D-30
- Features de janela móvel: média/std/min/max em 7, 14, 30 dias
- TimeSeriesSplit: Validação respeitando ordem temporal
- Optuna: Otimização bayesiana de hiperparâmetros
- Early stopping: Prevenir overfitting
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple

import holidays
import numpy as np
import pandas as pd
import structlog
from lightgbm import LGBMRegressor
from sklearn.model_selection import TimeSeriesSplit
from sklearn.preprocessing import StandardScaler
from sqlmodel import Session, select
import optuna

from app.core.database import engine
from app.ml.model_manager import ModelMetadata, save_model
from app.models.models import PrecosHistoricos, Produto, VendasHistoricas

LOGGER = structlog.get_logger(__name__)

# Configurações
MINIMUM_HISTORY_DAYS = 120  # Mínimo de 4 meses de histórico
VALIDATION_DAYS = 30  # Holdout final para validação
N_SPLITS_CV = 3  # Número de splits no TimeSeriesSplit
OPTUNA_TRIALS = 50  # Número de trials para otimização

# Feriados brasileiros
BR_HOLIDAYS = holidays.Brazil()


class InsufficientDataError(Exception):
    """Exceção lançada quando não há dados suficientes para treinamento."""


def _load_product_data(session: Session, sku: str) -> Tuple[Produto, pd.DataFrame]:
    """
    Carrega dados de preços e vendas de um produto.
    
    Returns:
        Tupla (produto, dataframe) com dados históricos
    """
    # Buscar produto
    produto = session.exec(select(Produto).where(Produto.sku == sku)).first()
    if not produto:
        raise ValueError(f"Produto com SKU '{sku}' não encontrado")
    
    # Carregar preços
    precos = list(
        session.exec(
            select(PrecosHistoricos)
            .where(PrecosHistoricos.produto_id == produto.id)
            .order_by(PrecosHistoricos.coletado_em)
        )
    )
    
    # Carregar vendas
    vendas = list(
        session.exec(
            select(VendasHistoricas)
            .where(VendasHistoricas.produto_id == produto.id)
            .order_by(VendasHistoricas.data_venda)
        )
    )
    
    if len(precos) < MINIMUM_HISTORY_DAYS:
        raise InsufficientDataError(
            f"Produto {sku} possui apenas {len(precos)} dias de histórico. "
            f"Mínimo necessário: {MINIMUM_HISTORY_DAYS}"
        )
    
    # Criar DataFrame de preços
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
    
    # Criar DataFrame de vendas
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
    
    # Merge preços e vendas
    df = df_prices.copy()
    if not df_sales.empty:
        df = df.merge(df_sales, on="date", how="left")
        df["quantity"] = df["quantity"].fillna(0)
    else:
        df["quantity"] = 0
    
    df = df.sort_values("date").reset_index(drop=True)
    
    return produto, df


def _engineer_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Cria features avançadas para séries temporais.
    
    Features criadas:
    - Calendário: dia da semana, mês, trimestre, dia do mês, semana do ano
    - Feriados: is_holiday, days_to_holiday, days_from_holiday
    - Lag: preços e vendas de D-1, D-2, D-7, D-14, D-30
    - Rolling: média, std, min, max em janelas de 7, 14, 30 dias
    """
    df = df.copy()
    df["date"] = pd.to_datetime(df["date"])
    df = df.set_index("date").asfreq("D")
    
    # Interpolar valores faltantes
    df["price"] = df["price"].interpolate(method="time").ffill().bfill()
    df["quantity"] = df["quantity"].fillna(0)
    
    df = df.reset_index()
    
    # ==========================
    # 1. FEATURES DE CALENDÁRIO
    # ==========================
    df["day_of_week"] = df["date"].dt.dayofweek  # 0=Monday, 6=Sunday
    df["day_of_month"] = df["date"].dt.day
    df["week_of_year"] = df["date"].dt.isocalendar().week.astype(int)
    df["month"] = df["date"].dt.month
    df["quarter"] = df["date"].dt.quarter
    df["is_weekend"] = (df["day_of_week"] >= 5).astype(int)
    df["is_month_start"] = df["date"].dt.is_month_start.astype(int)
    df["is_month_end"] = df["date"].dt.is_month_end.astype(int)
    
    # ==========================
    # 2. FEATURES DE FERIADOS
    # ==========================
    df["is_holiday"] = df["date"].apply(lambda x: x.date() in BR_HOLIDAYS).astype(int)
    
    # Dias até o próximo feriado e desde o último
    def days_to_next_holiday(date):
        for i in range(1, 31):  # Procurar nos próximos 30 dias
            future_date = date + timedelta(days=i)
            if future_date.date() in BR_HOLIDAYS:
                return i
        return 30
    
    def days_from_last_holiday(date):
        for i in range(1, 31):  # Procurar nos últimos 30 dias
            past_date = date - timedelta(days=i)
            if past_date.date() in BR_HOLIDAYS:
                return i
        return 30
    
    df["days_to_holiday"] = df["date"].apply(days_to_next_holiday)
    df["days_from_holiday"] = df["date"].apply(days_from_last_holiday)
    
    # ==========================
    # 3. FEATURES DE LAG
    # ==========================
    for lag in [1, 2, 7, 14, 30]:
        df[f"price_lag_{lag}"] = df["price"].shift(lag)
        df[f"quantity_lag_{lag}"] = df["quantity"].shift(lag)
    
    # ==========================
    # 4. FEATURES DE ROLLING WINDOW
    # ==========================
    for window in [7, 14, 30]:
        # Preço
        df[f"price_rolling_mean_{window}"] = df["price"].rolling(window).mean()
        df[f"price_rolling_std_{window}"] = df["price"].rolling(window).std()
        df[f"price_rolling_min_{window}"] = df["price"].rolling(window).min()
        df[f"price_rolling_max_{window}"] = df["price"].rolling(window).max()
        
        # Quantidade
        df[f"quantity_rolling_mean_{window}"] = df["quantity"].rolling(window).mean()
        df[f"quantity_rolling_std_{window}"] = df["quantity"].rolling(window).std()
        df[f"quantity_rolling_sum_{window}"] = df["quantity"].rolling(window).sum()
    
    # ==========================
    # 5. FEATURES DERIVADAS
    # ==========================
    # Razão preço atual vs. média móvel
    df["price_vs_ma7"] = df["price"] / (df["price_rolling_mean_7"] + 1e-6)
    df["price_vs_ma30"] = df["price"] / (df["price_rolling_mean_30"] + 1e-6)
    
    # Volatilidade recente
    df["price_volatility_7"] = df["price_rolling_std_7"] / (df["price_rolling_mean_7"] + 1e-6)
    
    # Remover linhas com NaN (das janelas e lags)
    df = df.dropna()
    
    return df


def _optimize_hyperparameters(
    X: pd.DataFrame,
    y: pd.Series,
    n_trials: int = OPTUNA_TRIALS,
) -> Dict:
    """
    Otimiza hiperparâmetros do LightGBM usando Optuna.
    
    Usa TimeSeriesSplit para validação cruzada respeitando ordem temporal.
    """
    LOGGER.info(f"Iniciando otimização de hiperparâmetros com {n_trials} trials...")
    
    def objective(trial: optuna.Trial) -> float:
        # Definir espaço de busca
        params = {
            "objective": "regression",
            "metric": "rmse",
            "verbosity": -1,
            "n_estimators": trial.suggest_int("n_estimators", 100, 1000),
            "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.3, log=True),
            "max_depth": trial.suggest_int("max_depth", 3, 12),
            "num_leaves": trial.suggest_int("num_leaves", 20, 200),
            "min_child_samples": trial.suggest_int("min_child_samples", 10, 100),
            "subsample": trial.suggest_float("subsample", 0.6, 1.0),
            "colsample_bytree": trial.suggest_float("colsample_bytree", 0.6, 1.0),
            "reg_alpha": trial.suggest_float("reg_alpha", 1e-8, 10.0, log=True),
            "reg_lambda": trial.suggest_float("reg_lambda", 1e-8, 10.0, log=True),
            "random_state": 42,
        }
        
        # Time Series Cross Validation
        tscv = TimeSeriesSplit(n_splits=N_SPLITS_CV)
        scores = []
        
        for train_idx, val_idx in tscv.split(X):
            X_train_fold, X_val_fold = X.iloc[train_idx], X.iloc[val_idx]
            y_train_fold, y_val_fold = y.iloc[train_idx], y.iloc[val_idx]
            
            model = LGBMRegressor(**params)
            model.fit(
                X_train_fold,
                y_train_fold,
                eval_set=[(X_val_fold, y_val_fold)],
                callbacks=[
                    optuna.integration.LightGBMPruningCallback(trial, "rmse")
                ],
            )
            
            y_pred = model.predict(X_val_fold)
            rmse = np.sqrt(np.mean((y_val_fold - y_pred) ** 2))
            scores.append(rmse)
        
        return np.mean(scores)
    
    # Criar estudo Optuna
    study = optuna.create_study(
        direction="minimize",
        sampler=optuna.samplers.TPESampler(seed=42),
    )
    
    study.optimize(
        objective,
        n_trials=n_trials,
        show_progress_bar=False,
        n_jobs=1,  # LightGBM já paraleliza internamente
    )
    
    LOGGER.info(f"Melhores hiperparâmetros encontrados: RMSE={study.best_value:.4f}")
    
    return study.best_params


def train_model_for_product(
    sku: str,
    optimize: bool = True,
    n_trials: int = OPTUNA_TRIALS,
) -> Dict:
    """
    Treina modelo especializado para um produto específico.
    
    Args:
        sku: SKU do produto
        optimize: Se True, otimiza hiperparâmetros com Optuna
        n_trials: Número de trials para otimização
    
    Returns:
        Dicionário com métricas de performance
    """
    LOGGER.info(f"Iniciando treinamento para produto: {sku}")
    
    with Session(engine) as session:
        # Carregar dados
        produto, df = _load_product_data(session, sku)
        LOGGER.info(f"Dados carregados: {len(df)} dias de histórico")
        
        # Feature engineering
        df_featured = _engineer_features(df)
        LOGGER.info(f"Features criadas: {len(df_featured)} amostras após feature engineering")
        
        # Separar features e target
        feature_cols = [col for col in df_featured.columns if col not in ["date", "price", "quantity"]]
        X = df_featured[feature_cols]
        y = df_featured["price"]
        
        LOGGER.info(f"Features utilizadas ({len(feature_cols)}): {feature_cols[:10]}...")
        
        # Holdout final para validação
        n_validation = VALIDATION_DAYS
        X_train_full, X_test = X.iloc[:-n_validation], X.iloc[-n_validation:]
        y_train_full, y_test = y.iloc[:-n_validation], y.iloc[-n_validation:]
        
        LOGGER.info(f"Split: {len(X_train_full)} treino, {len(X_test)} validação")
        
        # Otimizar hiperparâmetros (se solicitado)
        if optimize:
            best_params = _optimize_hyperparameters(X_train_full, y_train_full, n_trials=n_trials)
            best_params["random_state"] = 42
            best_params["objective"] = "regression"
            best_params["metric"] = "rmse"
            best_params["verbosity"] = -1
        else:
            # Hiperparâmetros padrão razoáveis
            best_params = {
                "objective": "regression",
                "metric": "rmse",
                "n_estimators": 500,
                "learning_rate": 0.05,
                "max_depth": 7,
                "num_leaves": 50,
                "min_child_samples": 20,
                "subsample": 0.8,
                "colsample_bytree": 0.8,
                "reg_alpha": 0.1,
                "reg_lambda": 0.1,
                "random_state": 42,
                "verbosity": -1,
            }
        
        # Treinar modelo final
        LOGGER.info("Treinando modelo final...")
        model = LGBMRegressor(**best_params)
        model.fit(X_train_full, y_train_full)
        
        # Avaliar no conjunto de teste
        y_pred_test = model.predict(X_test)
        rmse = np.sqrt(np.mean((y_test - y_pred_test) ** 2))
        mae = np.mean(np.abs(y_test - y_pred_test))
        mape = np.mean(np.abs((y_test - y_pred_test) / y_test)) * 100
        
        metrics = {
            "rmse": round(float(rmse), 4),
            "mae": round(float(mae), 4),
            "mape": round(float(mape), 4),
        }
        
        LOGGER.info(f"Métricas de validação: {metrics}")
        
        # Normalizar features (opcional, para melhor estabilidade)
        scaler = StandardScaler()
        scaler.fit(X_train_full)
        
        # Salvar modelo
        metadata = ModelMetadata(
            sku=sku,
            model_type="LightGBM",
            version=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
            hyperparameters=best_params,
            metrics=metrics,
            features=feature_cols,
            trained_at=datetime.now(timezone.utc).isoformat(),
            training_samples=len(X_train_full),
        )
        
        save_model(sku=sku, model=model, scaler=scaler, metadata=metadata)
        
        LOGGER.info(f"✅ Modelo treinado e salvo com sucesso para {sku}")
        
        return {
            "sku": sku,
            "success": True,
            "metrics": metrics,
            "training_samples": len(X_train_full),
            "validation_samples": len(X_test),
            "features_count": len(feature_cols),
        }


__all__ = [
    "train_model_for_product",
    "InsufficientDataError",
]
