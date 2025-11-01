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

ATUALIZAÇÃO v3.5 (Ultra Otimizado):
====================================
- Incorporado de scripts/train_advanced_models.py:
  * Tratamento inteligente de zeros (EWM)
  * Remoção de outliers com threshold ajustável
  * Feature engineering expandido (lags até 90 dias, encoding cíclico)
  * Ensemble stacking com LGBM/XGB/RF/GB + meta learner Ridge
  * Detecção automática de suporte a early_stopping no XGBoost
  * Persistência de metadados detalhados e dataset de treino
- Compatibilidade com xgboost==3.1.1 (sem early_stopping_rounds)
- Suporte a GPU (CUDA) quando disponível
- Métricas robustas: RMSE, MAE, MAPE, WMAPE
"""

from __future__ import annotations

import os
import warnings
import inspect
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

import holidays
import numpy as np
import pandas as pd
import pickle
import structlog
from lightgbm import LGBMRegressor
from sklearn.preprocessing import RobustScaler
from sklearn.model_selection import TimeSeriesSplit
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.metrics import mean_squared_error, mean_absolute_error
from sklearn.linear_model import Ridge
from sqlmodel import Session, select
import optuna
from optuna.samplers import TPESampler
from optuna.pruners import MedianPruner

# GPU Support
try:
    import xgboost as xgb
    from xgboost import XGBRegressor
    XGBOOST_AVAILABLE = True
except ImportError:
    XGBOOST_AVAILABLE = False

from app.core.database import engine
from app.ml.model_manager import ModelMetadata, save_model, get_model_dir
from app.models.models import PrecosHistoricos, Produto, VendasHistoricas, ModeloPredicao

warnings.filterwarnings("ignore")
LOGGER = structlog.get_logger(__name__)

# ======================================================================================
# 1) DETECÇÃO DE GPU / AMBIENTE
# ======================================================================================
def check_gpu_available() -> tuple[bool, str | None]:
    """Verifica GPU via nvidia-smi (dentro do container)."""
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            return True, result.stdout.strip().split("\n")[0]
    except Exception:
        pass
    return False, None

HAS_GPU, GPU_NAME = check_gpu_available()
USE_GPU = HAS_GPU

if HAS_GPU:
    LOGGER.info(f"🎮 GPU detectada: {GPU_NAME}")
else:
    LOGGER.info("🖥️  GPU não detectada (vamos usar CPU)")

# ======================================================================================
# 2) CONSTANTES E CONFIGURAÇÕES
# ======================================================================================
MINIMUM_HISTORY_DAYS = 120
FORECAST_HORIZON = 7
HOLDOUT_RATIO = 0.2
BACKTEST_SPLITS = 5
RANDOM_SEED = 42

# Thresholds ajustáveis para tratamento de dados
OUTLIER_STD_THRESHOLD = 3.0
ZERO_SEQUENCE_THRESHOLD = 3

# Diretório base para modelos (reutilizado do model_manager)
PROJECT_ROOT = Path(__file__).resolve().parents[2]

# Feriados brasileiros
BR_HOLIDAYS = holidays.Brazil()


# ======================================================================================
# 3) MÉTRICAS ROBUSTAS
# ======================================================================================
def mape_safe(y_true: np.ndarray, y_pred: np.ndarray, eps: float = 1.0) -> float:
    """
    MAPE seguro que ignora alvos muito pequenos.
    https://otexts.com/fpp3/accuracy.html
    """
    y_true = np.asarray(y_true)
    y_pred = np.asarray(y_pred)

    mask = np.abs(y_true) >= eps
    if not np.any(mask):
        return float("nan")

    y_true_f = y_true[mask]
    y_pred_f = y_pred[mask]
    return float(np.mean(np.abs((y_true_f - y_pred_f) / y_true_f)) * 100.0)


def wmape(y_true: np.ndarray, y_pred: np.ndarray, eps: float = 1e-6) -> float:
    """
    Weighted MAPE (WAPE) - comum em supply chain.
    """
    y_true = np.asarray(y_true)
    y_pred = np.asarray(y_pred)
    num = np.sum(np.abs(y_true - y_pred))
    den = np.sum(np.abs(y_true)) + eps
    return float(num / den * 100.0)


def eval_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> Dict[str, float]:
    mse = mean_squared_error(y_true, y_pred)
    rmse = float(np.sqrt(mse))
    mae = float(mean_absolute_error(y_true, y_pred))
    mape = mape_safe(y_true, y_pred, eps=1.0)
    wmape_val = wmape(y_true, y_pred)
    return {
        "rmse": rmse,
        "mae": mae,
        "mape": mape,
        "wmape": wmape_val,
    }


class InsufficientDataError(Exception):
    """Exceção lançada quando não há dados suficientes para treinamento."""


# ======================================================================================
# 4) DATAFRAME BASE DIÁRIO COM TRATAMENTO DE ZEROS E OUTLIERS
# ======================================================================================
def handle_zero_sales(df: pd.DataFrame, method: str = "smart") -> pd.DataFrame:
    """
    Tratamento inteligente de dias com vendas zeradas.
    
    Args:
        df: DataFrame com coluna 'quantidade'
        method: 'keep' (manter zeros), 'interpolate' (interpolar), 
                'smart' (substituir por média móvel se > ZERO_SEQUENCE_THRESHOLD dias consecutivos),
                'weighted' (média ponderada exponencial)
    """
    df = df.copy()
    
    if method == "keep":
        return df
    elif method == "interpolate":
        df["quantidade"] = df["quantidade"].replace(0, np.nan).interpolate(method="linear", limit=7)
        df["quantidade"] = df["quantidade"].fillna(0)
    elif method == "weighted":
        # Média ponderada exponencial dos últimos 14 dias (pesos maiores para dias mais recentes)
        mask = df["quantidade"] == 0
        if mask.any():
            ewm_values = df["quantidade"].ewm(span=14, adjust=False).mean()
            df.loc[mask, "quantidade"] = ewm_values[mask]
    elif method == "smart":
        # Identificar sequências longas de zeros (> ZERO_SEQUENCE_THRESHOLD dias consecutivos)
        zero_mask = df["quantidade"] == 0
        zero_groups = (zero_mask != zero_mask.shift()).cumsum()
        long_zero_sequences = zero_groups[zero_mask].value_counts()[lambda x: x > ZERO_SEQUENCE_THRESHOLD].index
        
        # Substituir sequências longas pela média móvel ponderada dos 14 dias anteriores
        for group in long_zero_sequences:
            group_mask = (zero_groups == group)
            if group_mask.sum() > 0:
                idx = group_mask[group_mask].index
                # Usar EWM para dar mais peso aos dias mais recentes
                ewm_values = df["quantidade"].ewm(span=14, adjust=False).mean()
                df.loc[idx, "quantidade"] = ewm_values.loc[idx]
    
    return df


def remove_outliers(df: pd.DataFrame, column: str = "quantidade", std_threshold: float = None) -> pd.DataFrame:
    """
    Remove outliers usando Z-score com threshold ajustável.
    
    Args:
        df: DataFrame
        column: Nome da coluna para detectar outliers
        std_threshold: Número de desvios padrão (usa OUTLIER_STD_THRESHOLD se None)
    """
    df = df.copy()
    
    if std_threshold is None:
        std_threshold = OUTLIER_STD_THRESHOLD
    
    if len(df) < 30:
        return df  # Dados insuficientes para detectar outliers
    
    mean = df[column].mean()
    std = df[column].std()
    
    if std == 0:
        return df
    
    z_scores = np.abs((df[column] - mean) / std)
    outlier_mask = z_scores > std_threshold
    
    # Substituir outliers pela mediana dos 7 dias adjacentes (janela mais robusta)
    for idx in df[outlier_mask].index:
        window_start = max(0, idx - 3)
        window_end = min(len(df), idx + 4)
        window_median = df.loc[window_start:window_end, column].median()
        df.loc[idx, column] = window_median
    
    return df


def build_base_dataframe(
    vendas: List[VendasHistoricas],
    precos: List[PrecosHistoricas],
) -> pd.DataFrame:
    if not vendas:
        raise ValueError("Sem vendas para montar dataframe base.")

    df_v = (
        pd.DataFrame(
            {
                "data_venda": [v.data_venda for v in vendas],
                "quantidade": [v.quantidade for v in vendas],
                "receita": [float(v.receita) for v in vendas],
            }
        )
        .groupby("data_venda")
        .agg({"quantidade": "sum", "receita": "sum"})
        .sort_index()
    )

    # força diário
    df_v = df_v.asfreq("D")

    if precos:
        df_p = (
            pd.DataFrame(
                {
                    "data_venda": [p.coletado_em for p in precos],
                    "preco": [float(p.preco) for p in precos],
                }
            )
            .groupby("data_venda")
            .agg({"preco": "mean"})
            .sort_index()
            .asfreq("D")
        )
        df = df_v.join(df_p, how="left")
    else:
        df = df_v
        df["preco"] = np.nan

    df["preco"] = df["preco"].ffill().bfill()
    df["quantidade"] = df["quantidade"].fillna(0)
    df["receita"] = df["receita"].fillna(0)

    df = df.reset_index()
    
    # Aplicar tratamentos
    df = handle_zero_sales(df, method="weighted")  # Usando média ponderada exponencial
    df = remove_outliers(df, column="quantidade", std_threshold=OUTLIER_STD_THRESHOLD)
    
    return df


# ======================================================================================
# 5) FEATURE ENGINEERING EXPANDIDO E OTIMIZADO
# ======================================================================================
def create_time_series_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Feature engineering expandido com lags até 90 dias e features estatísticas avançadas.
    """
    df = df.copy()

    # Lags expandidos (1, 7, 14, 30, 60, 90 dias)
    for lag in [1, 7, 14, 30, 60, 90]:
        df[f"lag_{lag}"] = df["quantidade"].shift(lag)

    # Rolling windows expandidos com min, max, mean, std (7, 14, 30, 60 dias)
    for window in [7, 14, 30, 60]:
        df[f"rolling_mean_{window}"] = df["quantidade"].rolling(window=window).mean()
        df[f"rolling_std_{window}"] = df["quantidade"].rolling(window=window).std().fillna(0)
        df[f"rolling_min_{window}"] = df["quantidade"].rolling(window=window).min()
        df[f"rolling_max_{window}"] = df["quantidade"].rolling(window=window).max()
        df[f"rolling_median_{window}"] = df["quantidade"].rolling(window=window).median()
        
        # Range (amplitude) das janelas
        df[f"rolling_range_{window}"] = df[f"rolling_max_{window}"] - df[f"rolling_min_{window}"]
        
        # Coeficiente de variação (CV)
        df[f"rolling_cv_{window}"] = (df[f"rolling_std_{window}"] / (df[f"rolling_mean_{window}"] + 1)).fillna(0)

    # Exponential weighted moving averages com diferentes spans
    for span in [7, 14, 30, 60]:
        df[f"ewm_mean_{span}"] = df["quantidade"].ewm(span=span).mean()
        df[f"ewm_std_{span}"] = df["quantidade"].ewm(span=span).std().fillna(0)

    # Features de calendário expandidas
    df["day_of_week"] = df["data_venda"].dt.dayofweek
    df["day_of_month"] = df["data_venda"].dt.day
    df["month"] = df["data_venda"].dt.month
    df["quarter"] = df["data_venda"].dt.quarter
    df["is_weekend"] = (df["day_of_week"] >= 5).astype(int)
    df["is_month_start"] = df["data_venda"].dt.is_month_start.astype(int)
    df["is_month_end"] = df["data_venda"].dt.is_month_end.astype(int)
    df["is_quarter_start"] = df["data_venda"].dt.is_quarter_start.astype(int)
    df["is_quarter_end"] = df["data_venda"].dt.is_quarter_end.astype(int)
    df["week_of_year"] = df["data_venda"].dt.isocalendar().week.astype(int)
    
    # Features cíclicas (encoding sinusoidal para capturar sazonalidade)
    df["day_of_week_sin"] = np.sin(2 * np.pi * df["day_of_week"] / 7)
    df["day_of_week_cos"] = np.cos(2 * np.pi * df["day_of_week"] / 7)
    df["month_sin"] = np.sin(2 * np.pi * df["month"] / 12)
    df["month_cos"] = np.cos(2 * np.pi * df["month"] / 12)
    df["day_of_month_sin"] = np.sin(2 * np.pi * df["day_of_month"] / 31)
    df["day_of_month_cos"] = np.cos(2 * np.pi * df["day_of_month"] / 31)

    # Features de tendência
    df["trend"] = np.arange(len(df))
    df["trend_squared"] = df["trend"] ** 2
    df["trend_cubed"] = df["trend"] ** 3

    # Features de preço expandidas
    df["preco_lag_1"] = df["preco"].shift(1)
    df["preco_lag_7"] = df["preco"].shift(7)
    df["preco_lag_14"] = df["preco"].shift(14)
    
    for window in [7, 14, 30, 60]:
        df[f"preco_mean_{window}"] = df["preco"].rolling(window=window).mean()
        df[f"preco_volatility_{window}"] = df["preco"].rolling(window=window).std().fillna(0)
        df[f"preco_min_{window}"] = df["preco"].rolling(window=window).min()
        df[f"preco_max_{window}"] = df["preco"].rolling(window=window).max()
    
    # Razões e interações (com proteção contra divisão por zero)
    df["preco_quantidade_ratio"] = df["preco"] / (df["quantidade"] + 1)
    df["quantidade_preco_interaction"] = df["quantidade"] * df["preco"]
    df["quantidade_change"] = df["quantidade"].pct_change().replace([np.inf, -np.inf], 0)
    df["preco_change"] = df["preco"].pct_change().replace([np.inf, -np.inf], 0)
    
    # Momentum (taxa de mudança)
    for window in [7, 14, 30]:
        df[f"quantidade_momentum_{window}"] = df["quantidade"].diff(window)
        df[f"preco_momentum_{window}"] = df["preco"].diff(window)

    # Features de diferenciação
    df["quantidade_diff_1"] = df["quantidade"].diff(1)
    df["quantidade_diff_7"] = df["quantidade"].diff(7)
    df["quantidade_diff_30"] = df["quantidade"].diff(30)

    # Remover NaN e valores infinitos
    df = df.replace([np.inf, -np.inf], np.nan)
    df = df.dropna()
    
    return df


def prepare_training_data(
    df: pd.DataFrame,
    forecast_horizon: int = FORECAST_HORIZON,
    target: str = "quantidade",
) -> Tuple[np.ndarray, np.ndarray, List[str]]:
    """Prepara dados de treino para modelo (suporta múltiplos targets).
    
    Args:
        df: DataFrame com features e target
        forecast_horizon: Dias à frente para prever
        target: Nome da coluna target (quantidade, preco, receita, lucro, margem, custo, etc)
    
    Targets Suportados:
        - quantidade: Demanda (unidades)
        - preco: Preço unitário (R$)
        - receita: preco × quantidade (R$)
        - lucro: (preco - custo) × quantidade (R$)
        - margem: (preco - custo) / preco × 100 (%)
        - custo: custo_unitario × quantidade (R$)
        - rotatividade: quantidade / estoque_médio (vezes)
        - dias_estoque: 30 / rotatividade (dias)
    """
    features_df = df.drop(
        columns=["quantidade", "data_venda", "preco", "receita"],
        errors="ignore",
    )
    
    # ✅ NOVO: Suporte escalável para múltiplos targets
    # Calcular targets derivados se necessário
    if target == "receita" and "receita" not in df.columns:
        df["receita"] = df["preco"] * df["quantidade"]
    elif target == "lucro":
        custo_unitario = df["preco"] * 0.6
        df["lucro"] = (df["preco"] - custo_unitario) * df["quantidade"]
    elif target == "margem":
        custo_unitario = df["preco"] * 0.6
        df["margem"] = ((df["preco"] - custo_unitario) / df["preco"]) * 100
    elif target == "custo":
        custo_unitario = df["preco"] * 0.6
        df["custo"] = custo_unitario * df["quantidade"]
    elif target == "rotatividade":
        estoque_medio = df["quantidade"].rolling(window=30, min_periods=1).mean()
        df["rotatividade"] = df["quantidade"] / (estoque_medio + 1)
    elif target == "dias_estoque":
        estoque_medio = df["quantidade"].rolling(window=30, min_periods=1).mean()
        rotatividade = df["quantidade"] / (estoque_medio + 1)
        df["dias_estoque"] = 30 / (rotatividade + 0.01)
    
    # Validar que o target existe
    if target not in df.columns:
        raise ValueError(
            f"Target '{target}' não encontrado. Disponíveis: "
            f"{df.columns.tolist()}"
        )
    
    y = df[target].shift(-forecast_horizon).dropna()
    X = features_df.iloc[:-forecast_horizon]

    min_len = min(len(X), len(y))
    X = X.iloc[:min_len]
    y = y.iloc[:min_len]

    # Validação adicional: remover inf/nan que possam ter escapado
    X = X.replace([np.inf, -np.inf], np.nan)
    
    # Identificar colunas com NaN
    nan_cols = X.columns[X.isna().any()].tolist()
    if nan_cols:
        # Substituir NaN pela mediana da coluna
        for col in nan_cols:
            X[col] = X[col].fillna(X[col].median())
    
    # Se ainda houver NaN (coluna toda NaN), preencher com 0
    X = X.fillna(0)
    
    # Validação final
    assert not np.any(np.isnan(X.values)), "X contém NaN após limpeza"
    assert not np.any(np.isinf(X.values)), "X contém inf após limpeza"

    return X.values, y.values, list(X.columns)


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
    
    if len(vendas) < MINIMUM_HISTORY_DAYS:
        raise InsufficientDataError(
            f"Produto {sku} possui apenas {len(vendas)} dias de histórico. "
            f"Mínimo necessário: {MINIMUM_HISTORY_DAYS}"
        )
    
    # Usar a nova função de dataframe base
    df = build_base_dataframe(vendas, precos)
    
    return produto, df


# ======================================================================================
# 6) XGBOOST: DETECÇÃO DE SUPORTE A EARLY STOPPING NA API SKLEARN
# ======================================================================================
def xgb_sklearn_supports_early_stopping() -> bool:
    """
    Checa se a tua instalação de xgboost permite:
        XGBRegressor().fit(..., early_stopping_rounds=..., eval_set=...)
    Na imagem Docker do Guilherme (xgboost==3.1.1) NÃO suporta.
    """
    try:
        sig = inspect.signature(xgb.XGBRegressor().fit)
        return "early_stopping_rounds" in sig.parameters
    except Exception:
        return False


XGB_SKLEARN_HAS_ES = xgb_sklearn_supports_early_stopping()
if not XGB_SKLEARN_HAS_ES:
    LOGGER.info("ℹ️  xgboost (sklearn API) sem early_stopping_rounds — usando treino simples no Optuna.")


# ======================================================================================
# 7) OBJETIVOS DO OPTUNA - OTIMIZADOS COM MAIS PARÂMETROS
# ======================================================================================
def objective_lgb(trial: optuna.Trial, X_train: np.ndarray, y_train: np.ndarray) -> float:
    """
    Objetivo otimizado para LightGBM com hiperparâmetros expandidos e mais exploração.
    """
    params = {
        "num_leaves": trial.suggest_int("num_leaves", 31, 255),  # Ampliado o range
        "max_depth": trial.suggest_int("max_depth", 4, 20),  # Aumentado para 20
        "learning_rate": trial.suggest_float("learning_rate", 0.005, 0.3, log=True),  # Ampliado
        "feature_fraction": trial.suggest_float("feature_fraction", 0.5, 1.0),
        "bagging_fraction": trial.suggest_float("bagging_fraction", 0.5, 1.0),
        "bagging_freq": trial.suggest_int("bagging_freq", 1, 10),
        "lambda_l1": trial.suggest_float("lambda_l1", 0.0, 10.0),
        "lambda_l2": trial.suggest_float("lambda_l2", 0.0, 10.0),
        "min_data_in_leaf": trial.suggest_int("min_data_in_leaf", 10, 100),
        "min_gain_to_split": trial.suggest_float("min_gain_to_split", 0.0, 2.0),
        "max_bin": trial.suggest_int("max_bin", 128, 512),  # Novo parâmetro
        "min_child_samples": trial.suggest_int("min_child_samples", 5, 100),  # Novo parâmetro
    }

    # Validação cruzada mais rigorosa (10 splits)
    tscv = TimeSeriesSplit(n_splits=10)
    scores: List[float] = []

    for tr_idx, val_idx in tscv.split(X_train):
        X_tr, X_val = X_train[tr_idx], X_train[val_idx]
        y_tr, y_val = y_train[tr_idx], y_train[val_idx]

        model = lgb.LGBMRegressor(
            **params,
            n_estimators=500,  # Aumentado de 300
            random_state=RANDOM_SEED,
            verbose=-1,
        )
        model.fit(
            X_tr,
            y_tr,
            eval_set=[(X_val, y_val)],
            eval_metric="rmse",
            callbacks=[lgb.early_stopping(stopping_rounds=50, verbose=False)],
        )
        y_pred = model.predict(X_val)
        m = eval_metrics(y_val, y_pred)
        scores.append(m["rmse"])

    return float(np.mean(scores))


def objective_xgb(trial: optuna.Trial, X_train: np.ndarray, y_train: np.ndarray) -> float:
    """
    Objetivo otimizado para XGBoost com hiperparâmetros expandidos e mais exploração.
    Versão compatível com xgboost==3.1.1 dentro do teu Docker.
    """
    params = {
        "max_depth": trial.suggest_int("max_depth", 3, 20),  # Aumentado para 20
        "learning_rate": trial.suggest_float("learning_rate", 0.005, 0.3, log=True),  # Ampliado
        "subsample": trial.suggest_float("subsample", 0.5, 1.0),
        "colsample_bytree": trial.suggest_float("colsample_bytree", 0.5, 1.0),
        "colsample_bylevel": trial.suggest_float("colsample_bylevel", 0.5, 1.0),  # Novo
        "colsample_bynode": trial.suggest_float("colsample_bynode", 0.5, 1.0),  # Novo
        "reg_alpha": trial.suggest_float("reg_alpha", 0.0, 10.0),
        "reg_lambda": trial.suggest_float("reg_lambda", 0.0, 10.0),
        "min_child_weight": trial.suggest_int("min_child_weight", 1, 10),
        "gamma": trial.suggest_float("gamma", 0.0, 10.0),  # Ampliado
        "max_delta_step": trial.suggest_int("max_delta_step", 0, 10),
    }

    # Validação cruzada mais rigorosa (10 splits)
    tscv = TimeSeriesSplit(n_splits=10)
    scores: List[float] = []

    for tr_idx, val_idx in tscv.split(X_train):
        X_tr, X_val = X_train[tr_idx], X_train[val_idx]
        y_tr, y_val = y_train[tr_idx], y_train[val_idx]

        # base params
        xgb_params = params.copy()
        xgb_params["n_estimators"] = 500  # Aumentado de 300
        xgb_params["random_state"] = RANDOM_SEED
        xgb_params["verbosity"] = 0
        xgb_params["tree_method"] = "hist"

        if USE_GPU:
            xgb_params["device"] = "cuda"

        model = xgb.XGBRegressor(**xgb_params)

        if XGB_SKLEARN_HAS_ES:
            # caminho "rico" (quando a build suporta)
            try:
                model.fit(
                    X_tr,
                    y_tr,
                    eval_set=[(X_val, y_val)],
                    eval_metric="rmse",
                    early_stopping_rounds=50,
                    verbose=False,
                )
            except TypeError:
                # mesmo se for detectado, mas a lib não aceitar, volta pro caminho simples
                model.fit(X_tr, y_tr, verbose=False)
        else:
            # caminho compatível com tua build
            model.fit(X_tr, y_tr, verbose=False)

        y_pred = model.predict(X_val)
        m = eval_metrics(y_val, y_pred)
        scores.append(m["rmse"])

    return float(np.mean(scores))


# ======================================================================================
# 8) STACKING COM OOF
# ======================================================================================
def build_stacking_with_oof(
    X_train: np.ndarray,
    y_train: np.ndarray,
    X_val: np.ndarray,
    y_val: np.ndarray,
    best_params_lgb: Dict[str, Any],
    best_params_xgb: Dict[str, Any],
) -> Dict[str, Any]:
    # LightGBM sempre CPU
    lgb_params_final = best_params_lgb.copy()

    # XGBoost: vamos tentar GPU
    xgb_params_final = best_params_xgb.copy()
    xgb_params_final["n_estimators"] = 500  # Aumentado
    xgb_params_final["random_state"] = RANDOM_SEED
    xgb_params_final["verbosity"] = 0
    xgb_params_final["tree_method"] = "hist"
    if USE_GPU:
        xgb_params_final["device"] = "cuda"

    base_models = {
        "lgb": lgb.LGBMRegressor(
            **lgb_params_final,
            n_estimators=500,  # Aumentado
            random_state=RANDOM_SEED,
            verbose=-1,
        ),
        "xgb": xgb.XGBRegressor(**xgb_params_final),
        "rf": RandomForestRegressor(
            n_estimators=300,  # Aumentado de 200
            max_depth=20,  # Aumentado de 15
            min_samples_split=5,
            min_samples_leaf=2,
            random_state=RANDOM_SEED,
            n_jobs=-1,
        ),
        "gb": GradientBoostingRegressor(
            n_estimators=300,  # Aumentado de 200
            max_depth=7,  # Aumentado de 5
            learning_rate=0.05,  # Reduzido para mais estabilidade
            subsample=0.8,
            random_state=RANDOM_SEED,
        ),
    }

    tscv = TimeSeriesSplit(n_splits=5)  # Aumentado de 3 para 5
    oof_preds = []
    oof_y = []

    for tr_idx, oof_idx in tscv.split(X_train):
        X_tr, X_oof = X_train[tr_idx], X_train[oof_idx]
        y_tr, y_oof = y_train[tr_idx], y_train[oof_idx]

        fold_preds = []
        for m in base_models.values():
            m.fit(X_tr, y_tr)
            fold_preds.append(m.predict(X_oof))

        oof_preds.append(np.column_stack(fold_preds))
        oof_y.append(y_oof)

    meta_train = np.vstack(oof_preds)
    meta_y = np.concatenate(oof_y)

    # predição no holdout real
    meta_val = np.column_stack([m.predict(X_val) for m in base_models.values()])

    meta_learner = Ridge(alpha=1.0)
    meta_learner.fit(meta_train, meta_y)
    y_pred_val = meta_learner.predict(meta_val)
    holdout_metrics = eval_metrics(y_val, y_pred_val)

    return {
        "base_models": base_models,
        "meta_learner": meta_learner,
        "holdout_metrics": holdout_metrics,
    }


# ======================================================================================
# 9) TREINO POR PRODUTO (INTERFACE ATUALIZADA)
# ======================================================================================
def train_model_for_product(
    sku: str,
    optimize: bool = True,
    n_trials: int = 50,
    backtest: bool = True,
    target: str = "quantidade",
    use_all_data: bool = False,
) -> Dict:
    """
    Treina modelo especializado para um produto específico.
    
    Args:
        sku: SKU do produto
        optimize: Se True, otimiza hiperparâmetros com Optuna
        n_trials: Número de trials para otimização
        backtest: Se True, executa backtest deslizante
        target: Target para treinar (quantidade, preco, receita, lucro, margem, custo, etc)
        use_all_data: Se True, usa 100% dos dados (sem split 80/20)
    
    Returns:
        Dicionário com métricas de performance e informações do modelo
    """
    LOGGER.info(f"Iniciando treinamento para produto: {sku} (target: {target})")
    
    # Targets suportados
    VALID_TARGETS = [
        "quantidade", "preco", "receita", "lucro", "margem", 
        "custo", "rotatividade", "dias_estoque"
    ]
    
    if target not in VALID_TARGETS:
        raise ValueError(
            f"target '{target}' inválido. Válidos: {', '.join(VALID_TARGETS)}"
        )
    
    try:
        with Session(engine) as session:
            # Carregar dados
            produto, df = _load_product_data(session, sku)
            LOGGER.info(f"Dados carregados: {len(df)} dias de histórico")
            
            # Feature engineering expandido
            df = create_time_series_features(df)
            LOGGER.info(f"Features criadas: {len(df)} amostras após feature engineering")
            
            if len(df) < MINIMUM_HISTORY_DAYS:
                raise InsufficientDataError(
                    f"Produto {sku} possui apenas {len(df)} amostras após feature engineering. "
                    f"Mínimo necessário: {MINIMUM_HISTORY_DAYS}"
                )
            
            # Preparar dados de treino
            X, y, feature_names = prepare_training_data(df, target=target)
            
            # ✅ NOVO: Suporte para usar TODOS os dados
            if use_all_data:
                # Usar 100% dos dados para treino
                X_train, X_val = X, X[:0]  # val vazio
                y_train, y_val = y, y[:0]  # val vazio
                LOGGER.info(f"Usando 100% dos dados ({len(X)} amostras)")
            else:
                # Split holdout tradicional 80/20
                split_idx = int(len(X) * (1 - HOLDOUT_RATIO))
                X_train, X_val = X[:split_idx], X[split_idx:]
                y_train, y_val = y[:split_idx], y[split_idx:]
            
            LOGGER.info(f"Split: {len(X_train)} treino, {len(X_val)} validação")
            
            # Normalização
            scaler = RobustScaler()
            X_train_scaled = scaler.fit_transform(X_train)
            X_val_scaled = scaler.transform(X_val)
            
            small_data = len(X_train_scaled) < 120
            
            # ----------------- Optuna -----------------
            if optimize and not small_data:
                LOGGER.info(f"🔧 {sku} - Otimizando hiperparâmetros (n_trials={n_trials})...")
                # LightGBM
                study_lgb = optuna.create_study(
                    sampler=TPESampler(seed=RANDOM_SEED),
                    pruner=MedianPruner(),
                    direction="minimize",
                )
                study_lgb.optimize(
                    lambda t: objective_lgb(t, X_train_scaled, y_train),
                    n_trials=n_trials,
                    show_progress_bar=False,
                )
                best_params_lgb = study_lgb.best_params
                best_rmse_lgb = study_lgb.best_value

                # XGBoost
                study_xgb = optuna.create_study(
                    sampler=TPESampler(seed=RANDOM_SEED),
                    pruner=MedianPruner(),
                    direction="minimize",
                )
                study_xgb.optimize(
                    lambda t: objective_xgb(t, X_train_scaled, y_train),
                    n_trials=n_trials,
                    show_progress_bar=False,
                )
                best_params_xgb = study_xgb.best_params
                best_rmse_xgb = study_xgb.best_value
            else:
                LOGGER.info(f"ℹ️ {sku} - pouca amostra ou optimize off, usando defaults.")
                best_params_lgb = {
                    "num_leaves": 64,
                    "max_depth": 8,
                    "learning_rate": 0.05,
                    "feature_fraction": 0.9,
                    "bagging_fraction": 0.8,
                    "bagging_freq": 5,
                    "lambda_l1": 0.0,
                    "lambda_l2": 0.0,
                    "min_data_in_leaf": 20,
                }
                best_rmse_lgb = None

                best_params_xgb = {
                    "max_depth": 8,
                    "learning_rate": 0.05,
                    "subsample": 0.9,
                    "colsample_bytree": 0.9,
                    "reg_alpha": 0.0,
                    "reg_lambda": 1.0,
                    "min_child_weight": 1,
                }
                best_rmse_xgb = None

            # ----------------- Stacking -----------------
            stacking_result = build_stacking_with_oof(
                X_train_scaled,
                y_train,
                X_val_scaled,
                y_val,
                best_params_lgb,
                best_params_xgb,
            )
            holdout_metrics = stacking_result["holdout_metrics"]

            # ----------------- Backtest -----------------
            backtest_metrics: List[Dict[str, float]] = []
            if backtest:
                backtest_metrics = sliding_backtest(
                    X,
                    y,
                    scaler,
                    best_params_lgb,
                    n_splits=BACKTEST_SPLITS,
                )

            # ----------------- Persistência -----------------
            model_dir = get_model_dir(sku)
            
            # Salvar modelos (ensemble stacking)
            with open(model_dir / "ensemble_base.pkl", "wb") as f:
                pickle.dump(stacking_result["base_models"], f)

            with open(model_dir / "meta_learner.pkl", "wb") as f:
                pickle.dump(stacking_result["meta_learner"], f)

            with open(model_dir / "scaler.pkl", "wb") as f:
                pickle.dump(scaler, f)

            # Salvar dataset usado
            df.to_parquet(model_dir / "training_data.parquet", index=False)

            # Metadados detalhados
            metadata = ModelMetadata(
                sku=sku,
                model_type="ensemble_stacking",
                version="3.5_ultra_optimized",
                hyperparameters={
                    "lgb": best_params_lgb,
                    "xgb": best_params_xgb,
                    "target": target,  # Adicionar target aos hiperparâmetros
                },
                metrics=holdout_metrics,
                features=feature_names,
                trained_at=datetime.now(timezone.utc).isoformat(),
                training_samples=len(X),
            )

            # Usar model_manager para persistência
            save_model(sku, stacking_result["base_models"], scaler, metadata)
            
            # Salvar também o meta learner e dataset
            with open(model_dir / "meta_learner.pkl", "wb") as f:
                pickle.dump(stacking_result["meta_learner"], f)
            df.to_parquet(model_dir / "training_data.parquet", index=False)

            # Log amigável
            msg = (
                f"    ✅ {sku} - HOLDOUT: "
                f"RMSE={holdout_metrics['rmse']:.4f} "
                f"MAE={holdout_metrics['mae']:.4f}"
            )
            mape_val = holdout_metrics.get("mape")
            if mape_val is not None and not np.isnan(mape_val):
                msg += f" MAPE={mape_val:.2f}%"
            else:
                msg += " MAPE=IGNORADO(ZEROS)"

            msg += f" WMAPE={holdout_metrics['wmape']:.2f}%"
            LOGGER.info(msg)

            if optimize and not small_data:
                LOGGER.info(
                    f"       (search) lgb_rmse_cv={best_rmse_lgb:.4f} | "
                    f"(search) xgb_rmse_cv={best_rmse_xgb:.4f}"
                )

            return {
                "sku": sku,
                "status": "success",
                "metrics": holdout_metrics,
                "training_samples": len(X),
                "validation_samples": len(X_val),
                "feature_count": len(feature_names),
                "model_type": "ensemble_stacking",
                "version": "3.5_ultra_optimized",
                "optimized": optimize and not small_data,
                "backtest_metrics": backtest_metrics if backtest else [],
                "training_time": datetime.now(timezone.utc).isoformat(),
            }

    except InsufficientDataError as e:
        LOGGER.warning(f"⚠️ {sku} - Dados insuficientes: {str(e)}")
        return {
            "sku": sku,
            "status": "insufficient_data",
            "error": str(e),
        }
    except Exception as e:
        LOGGER.error(f"❌ {sku} - Erro no treinamento: {str(e)}")
        return {
            "sku": sku,
            "status": "error",
            "error": str(e),
        }


# ======================================================================================
# 10) BACKTEST
# ======================================================================================
def sliding_backtest(
    X: np.ndarray,
    y: np.ndarray,
    scaler: RobustScaler,
    best_params_lgb: Dict[str, Any],
    n_splits: int = BACKTEST_SPLITS,
) -> List[Dict[str, float]]:
    if len(X) < 60:
        return []

    tscv = TimeSeriesSplit(n_splits=n_splits)
    results: List[Dict[str, float]] = []

    for tr_idx, val_idx in tscv.split(X):
        X_tr, X_t = X[tr_idx], X[val_idx]
        y_tr, y_t = y[tr_idx], y[val_idx]

        X_tr = scaler.transform(X_tr)
        X_t = scaler.transform(X_t)

        model = lgb.LGBMRegressor(
            **best_params_lgb,
            n_estimators=200,
            random_state=RANDOM_SEED,
            verbose=-1,
        )
        model.fit(X_tr, y_tr)
        y_pred = model.predict(X_t)
        results.append(eval_metrics(y_t, y_pred))

    return results


__all__ = [
    "train_model_for_product",
    "InsufficientDataError",
    "build_base_dataframe",
    "create_time_series_features",
    "prepare_training_data",
    "eval_metrics",
    "handle_zero_sales",
    "remove_outliers",
    "objective_lgb",
    "objective_xgb",
    "build_stacking_with_oof",
    "sliding_backtest",
]
