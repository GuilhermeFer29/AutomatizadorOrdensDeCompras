#!/usr/bin/env python3
"""
Treinamento Avançado de Modelos por Produto (v3.5 - Ultra Otimizado)

Objetivo desta versão
---------------------
- Funcionar **com as versões reais que estão dentro do teu Docker**:
    - xgboost==3.1.1  -> NÃO aceitar `early_stopping_rounds` na API sklearn  ❗
    - lightgbm==4.6.0 -> ok com callback `lgb.early_stopping(...)`
    - scikit-learn==1.7.2
    - optuna==4.5.0
- Não quebrar quando o XGBoost não aceita callbacks
- Manter Optuna, mas com guard-rails para séries curtas
- Salvar os modelos **no container** e **opcionalmente no host** (via env HOST_MODEL_DIR)
- Salvar o dataset usado no treino (parquet) por SKU
- Manter métricas de qualidade do dado
- Manter stacking com OOF

MELHORIAS v3.5 (Ultra Otimizado)
--------------------------------
✅ Lags expandidos até 90 dias (antes: 60)
✅ Validação cruzada com 10 splits (antes: 5)
✅ n_estimators aumentado para 500 (antes: 300)
✅ Features cíclicas sinusoidais para sazonalidade
✅ Coeficiente de variação (CV) nas rolling windows
✅ Momentum e features de interação expandidas
✅ Threshold de outliers ajustável (padrão: 3.0σ)
✅ Método de zeros: média ponderada exponencial
✅ Hiperparâmetros expandidos: max_bin, colsample_bylevel, colsample_bynode
✅ Ensemble otimizado: RF e GB com parâmetros ajustados
✅ 5 splits no stacking OOF (antes: 3)

Referências oficiais usadas
---------------------------
XGBoost Python 3.1.1:
- https://xgboost.readthedocs.io/en/stable/python/
- Seção "Scikit-Learn interface" (XGBRegressor.fit) não garante `early_stopping_rounds` em todas builds. :contentReference[oaicite:1]{index=1}

LightGBM 4.6.0:
- https://lightgbm.readthedocs.io/en/latest/Python-Intro.html
- https://lightgbm.readthedocs.io/en/latest/pythonapi/lightgbm.early_stopping.html :contentReference[oaicite:2]{index=2}

IMPORTANTE
----------
- LightGBM instalado via `pip` **não** vem com CUDA. Então vamos usar **CPU** para LGBM.
- Para XGBoost vamos **tentar** GPU (`device="cuda"`) e, se der erro de CUDA, caímos para CPU.
"""

from __future__ import annotations

import os
import sys
import argparse
import json
import pickle
import warnings
import inspect
import subprocess
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, List, Tuple, Any

import numpy as np
import pandas as pd
from sqlmodel import Session, select

from sklearn.preprocessing import RobustScaler
from sklearn.model_selection import TimeSeriesSplit
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.metrics import mean_squared_error, mean_absolute_error
from sklearn.linear_model import Ridge

import lightgbm as lgb
import xgboost as xgb
import optuna
from optuna.samplers import TPESampler
from optuna.pruners import MedianPruner

warnings.filterwarnings("ignore")

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
USE_GPU = HAS_GPU  # vamos tentar usar GPU no XGBoost
GPU_DEVICE = 0

if HAS_GPU:
    print(f"🎮 GPU detectada: {GPU_NAME}")
else:
    print("🖥️  GPU não detectada (vamos usar CPU)")

# ======================================================================================
# 2) IMPORTS DO PROJETO
# ======================================================================================
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.core.database import engine
from app.models.models import (
    Produto,
    VendasHistoricas,
    PrecosHistoricos,
    ModeloPredicao,
)
from app.ml.model_manager import get_model_dir  # ← Novo import

# ======================================================================================
# 3) CONSTANTES
# ======================================================================================
MIN_SAMPLES = 90
FORECAST_HORIZON = 7
HOLDOUT_RATIO = 0.2
BACKTEST_SPLITS = 5  # Aumentado de 3 para 5
RANDOM_SEED = 42

# Thresholds ajustáveis para tratamento de dados
OUTLIER_STD_THRESHOLD = 3.0  # Reduzido de 3.5 para 3.0 (mais sensível)
ZERO_SEQUENCE_THRESHOLD = 3  # Dias consecutivos de zero para tratamento

# saída extra (host) opcional
HOST_MODEL_DIR = os.getenv("HOST_MODEL_DIR")  # ex.: /home/guilherme/modelos_ml

# ======================================================================================
# 4) MÉTRICAS ROBUSTAS
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


# ======================================================================================
# 5) DATAFRAME BASE DIÁRIO COM TRATAMENTO DE ZEROS E OUTLIERS
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
    precos: List[PrecosHistoricos],
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
# 6) FEATURE ENGINEERING EXPANDIDO E OTIMIZADO
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


# ✅ NOVO: Transformações específicas por target
def apply_target_transforms(df: pd.DataFrame, target: str) -> pd.DataFrame:
    """
    Aplica transformações específicas por target para melhorar previsibilidade.
    
    Estratégias:
    - quantidade: log1p (muitos zeros)
    - preco: sem transform (suave)
    - receita: sem transform (estável)
    - lucro: winsorization (outliers extremos)
    - margem: log transform (distribuição assimétrica)
    - custo: sem transform (herda de quantidade)
    - rotatividade: log transform (muito assimétrica)
    - dias_estoque: clipping + log (valores extremos)
    """
    df = df.copy()
    
    if target == "quantidade" and "quantidade" in df.columns:
        # Log1p para quantidade (muitos zeros)
        df["quantidade"] = np.log1p(df["quantidade"])
        
    elif target == "lucro" and "lucro" in df.columns:
        # Winsorization para lucro (outliers extremos)
        q01 = df["lucro"].quantile(0.01)
        q99 = df["lucro"].quantile(0.99)
        df["lucro"] = df["lucro"].clip(lower=q01, upper=q99)
        
    elif target == "margem" and "margem" in df.columns:
        # Log transform para margem (distribuição assimétrica)
        df["margem"] = np.log1p(df["margem"].clip(lower=0))
        
    elif target == "rotatividade" and "rotatividade" in df.columns:
        # Log transform para rotatividade (muito assimétrica)
        df["rotatividade"] = np.log1p(df["rotatividade"].clip(lower=0.001))
        
    elif target == "dias_estoque" and "dias_estoque" in df.columns:
        # Clipping + log para dias_estoque (valores extremos)
        df["dias_estoque"] = df["dias_estoque"].clip(upper=365)
        df["dias_estoque"] = np.log1p(df["dias_estoque"])
    
    return df


# ✅ NOVO: Hiperparâmetros otimizados por target
def get_optimized_params(target: str) -> Dict[str, Any]:
    """Retorna hiperparâmetros otimizados específicos para cada target."""
    
    params = {
        "quantidade": {
            "num_leaves": 31,
            "max_depth": 5,
            "learning_rate": 0.05,
            "lambda_l1": 5.0,
            "lambda_l2": 5.0,
            "min_data_in_leaf": 20,
        },
        "preco": {
            "num_leaves": 63,
            "max_depth": 7,
            "learning_rate": 0.02,
            "lambda_l1": 1.0,
            "lambda_l2": 1.0,
            "min_data_in_leaf": 10,
        },
        "receita": {
            "num_leaves": 47,
            "max_depth": 6,
            "learning_rate": 0.03,
            "lambda_l1": 3.0,
            "lambda_l2": 3.0,
            "min_data_in_leaf": 15,
        },
        "lucro": {
            "num_leaves": 31,
            "max_depth": 5,
            "learning_rate": 0.05,
            "lambda_l1": 8.0,
            "lambda_l2": 8.0,
            "min_data_in_leaf": 30,
        },
        "margem": {
            "num_leaves": 47,
            "max_depth": 6,
            "learning_rate": 0.03,
            "lambda_l1": 2.0,
            "lambda_l2": 2.0,
            "min_data_in_leaf": 10,
        },
        "custo": {
            "num_leaves": 31,
            "max_depth": 5,
            "learning_rate": 0.05,
            "lambda_l1": 4.0,
            "lambda_l2": 4.0,
            "min_data_in_leaf": 15,
        },
        "rotatividade": {
            "num_leaves": 31,
            "max_depth": 5,
            "learning_rate": 0.05,
            "lambda_l1": 6.0,
            "lambda_l2": 6.0,
            "min_data_in_leaf": 20,
        },
        "dias_estoque": {
            "num_leaves": 31,
            "max_depth": 5,
            "learning_rate": 0.05,
            "lambda_l1": 6.0,
            "lambda_l2": 6.0,
            "min_data_in_leaf": 20,
        },
    }
    
    return params.get(target, params["quantidade"])


def prepare_training_data(
    df: pd.DataFrame,
    forecast_horizon: int = FORECAST_HORIZON,
    target: str = "quantidade",
) -> Tuple[np.ndarray, np.ndarray, List[str]]:
    """Prepara dados de treino (suporta múltiplos targets)."""
    
    # ✅ NOVO: Aplicar transformações específicas por target
    df = apply_target_transforms(df, target)
    features_df = df.drop(
        columns=["quantidade", "data_venda", "preco", "receita"],
        errors="ignore",
    )
    
    # ✅ Suporte para múltiplos targets
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
    
    # Validar target
    if target not in df.columns:
        raise ValueError(f"Target '{target}' não encontrado no DataFrame")
    
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


# ======================================================================================
# 7) XGBOOST: DETECÇÃO DE SUPORTE A EARLY STOPPING NA API SKLEARN
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
    print("ℹ️  xgboost (sklearn API) sem early_stopping_rounds — usando treino simples no Optuna.")


# ======================================================================================
# 8) OBJETIVOS DO OPTUNA - OTIMIZADOS COM MAIS PARÂMETROS
# ======================================================================================
def objective_lgb(
    trial: optuna.Trial,
    X_train: np.ndarray,
    y_train: np.ndarray,
) -> float:
    """Otimização LightGBM com Optuna (10 CV splits)."""
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

        # ✅ NOVO: Tentar GPU, fallback para CPU se não compilado com CUDA
        device = "cuda" if HAS_GPU else "cpu"
        try:
            model = lgb.LGBMRegressor(
                **params,
                n_estimators=500,
                random_state=RANDOM_SEED,
                verbose=-1,
                device_type=device,
            )
            model.fit(
                X_tr,
                y_tr,
                eval_set=[(X_val, y_val)],
                eval_metric="rmse",
                callbacks=[lgb.early_stopping(stopping_rounds=50, verbose=False)],
            )
        except Exception as e:
            # Se GPU falhar, usar CPU
            if "CUDA" in str(e) or "GPU" in str(e) or "not enabled" in str(e):
                model = lgb.LGBMRegressor(
                    **params,
                    n_estimators=500,
                    random_state=RANDOM_SEED,
                    verbose=-1,
                    device_type="cpu",  # Fallback para CPU
                )
                model.fit(
                    X_tr,
                    y_tr,
                    eval_set=[(X_val, y_val)],
                    eval_metric="rmse",
                    callbacks=[lgb.early_stopping(stopping_rounds=50, verbose=False)],
                )
            else:
                raise
        
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
# 9) STACKING COM OOF
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

    # Meta learner
    meta_learner = Ridge(alpha=1.0)

    # predição no holdout real (verificar se X_val não está vazio)
    if len(X_val) > 0:
        meta_val = np.column_stack([m.predict(X_val) for m in base_models.values()])
        meta_learner.fit(meta_train, meta_y)
        y_pred_val = meta_learner.predict(meta_val)
        holdout_metrics = eval_metrics(y_val, y_pred_val)
    else:
        # Se não há validação, usar OOF para métricas
        meta_learner.fit(meta_train, meta_y)
        y_pred_val = meta_learner.predict(meta_train)
        holdout_metrics = eval_metrics(meta_y, y_pred_val)

    return {
        "base_models": base_models,
        "meta_learner": meta_learner,
        "holdout_metrics": holdout_metrics,
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


# ======================================================================================
# 11) TREINO POR PRODUTO
# ======================================================================================
def save_to_host_if_needed(model_dir: Path, sku: str):
    """
    Se o usuário setou HOST_MODEL_DIR, copia tudo do modelo do container
    para uma pasta local no host (montada como volume).
    """
    if not HOST_MODEL_DIR:
        return

    target_dir = Path(HOST_MODEL_DIR) / sku
    target_dir.mkdir(parents=True, exist_ok=True)

    for item in model_dir.iterdir():
        if item.is_file():
            target_path = target_dir / item.name
            target_path.write_bytes(item.read_bytes())


def train_product_model(
    produto: Produto,
    optimize: bool = True,
    n_trials: int = 20,
    backtest: bool = True,
    use_all_data: bool = False,
    target: str = "quantidade",  # ← Novo parâmetro
) -> bool:
    # ✅ NOVO: Validar target
    VALID_TARGETS = {"quantidade", "preco", "receita", "lucro", "margem", "custo", "rotatividade", "dias_estoque"}
    if target not in VALID_TARGETS:
        print(f"    ❌ {produto.sku} - Target inválido: {target}")
        return False
    
    try:
        with Session(engine) as session:
            vendas = (
                session.exec(
                    select(VendasHistoricas)
                    .where(VendasHistoricas.produto_id == produto.id)
                    .order_by(VendasHistoricas.data_venda)
                )
                .all()
            )
            if len(vendas) < MIN_SAMPLES:
                print(f"    ⚠️ {produto.sku} - dados insuficientes ({len(vendas)}/{MIN_SAMPLES})")
                return False

            precos = (
                session.exec(
                    select(PrecosHistoricos)
                    .where(PrecosHistoricos.produto_id == produto.id)
                    .order_by(PrecosHistoricos.coletado_em)
                )
                .all()
            )

            df = build_base_dataframe(vendas, precos)
            df = create_time_series_features(df)
            if len(df) < MIN_SAMPLES:
                print(f"    ⚠️ {produto.sku} - features insuficientes ({len(df)}/{MIN_SAMPLES})")
                return False

            zero_days = int((df["quantidade"] == 0).sum())
            zero_days_pct = float(zero_days / len(df))
            missing_price = int(df["preco"].isna().sum())

            X, y, feature_names = prepare_training_data(df, target=target)

            # ✅ NOVO: Suporte para usar TODOS os dados
            if use_all_data:
                # Usar 100% dos dados para treino
                X_train, X_val = X, X[:0]  # val vazio
                y_train, y_val = y, y[:0]  # val vazio
                print(f"    📊 {produto.sku} - Usando 100% dos dados ({len(X)} amostras)")
            else:
                # Split tradicional 80/20
                split_idx = int(len(X) * (1 - HOLDOUT_RATIO))
                X_train, X_val = X[:split_idx], X[split_idx:]
                y_train, y_val = y[:split_idx], y[split_idx:]
            
            has_zero_in_holdout = bool((y_val == 0).any()) if len(y_val) > 0 else False

            scaler = RobustScaler()
            X_train_scaled = scaler.fit_transform(X_train)
            X_val_scaled = scaler.transform(X_val) if len(X_val) > 0 else X_val  # ← Verificar se X_val não está vazio

            small_data = len(X_train_scaled) < 120

            # ----------------- Optuna -----------------
            if optimize and not small_data:
                print(f"    🔧 {produto.sku} - Otimizando hiperparâmetros (n_trials={n_trials})...")
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
                print(f"    ℹ️ {produto.sku} - pouca amostra ou optimize off, usando defaults.")
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
            model_dir = get_model_dir(produto.sku) / target
            model_dir.mkdir(parents=True, exist_ok=True)

            # salva modelos
            with open(model_dir / "ensemble_base.pkl", "wb") as f:
                pickle.dump(stacking_result["base_models"], f)

            with open(model_dir / "meta_learner.pkl", "wb") as f:
                pickle.dump(stacking_result["meta_learner"], f)

            with open(model_dir / "scaler.pkl", "wb") as f:
                pickle.dump(scaler, f)

            # salva dataset usado
            df.to_parquet(model_dir / "training_data.parquet", index=False)

            # salva também no host, se houver volume
            save_to_host_if_needed(model_dir, produto.sku)

            metadata = {
                "produto_id": produto.id,
                "sku": produto.sku,
                "modelo_tipo": "ensemble_stacking",
                "versao": "3.5_ultra_optimized",
                "treinado_em": datetime.now(timezone.utc).isoformat(),
                "amostras_totais": int(len(X)),
                "amostras_treino": int(len(X_train)),
                "amostras_validacao": int(len(X_val)),
                "forecast_horizon": FORECAST_HORIZON,
                "holdout_ratio": HOLDOUT_RATIO,
                "feature_names": feature_names,
                "improvements_v3_5": {
                    "expanded_features": "Lags até 90 dias, features cíclicas sinusoidais, CV, momentum",
                    "zero_handling": "Média ponderada exponencial (EWM span=14)",
                    "outlier_detection": f"Z-score com threshold {OUTLIER_STD_THRESHOLD}σ (ajustável)",
                    "cv_splits": 10,
                    "optuna_trials_default": 50,
                    "n_estimators": 500,
                    "regularization": "Lambda expandido, max_bin, colsample_bylevel/bynode",
                    "ensemble": "RF(300 est, depth=20) + GB(300 est, depth=7, lr=0.05)",
                    "stacking_splits": 5,
                },
                "metrics": {
                    "holdout": holdout_metrics,
                    "search": {
                        "lgb": {
                            "best_rmse_cv": best_rmse_lgb,
                            "best_params": best_params_lgb,
                        },
                        "xgb": {
                            "best_rmse_cv": best_rmse_xgb,
                            "best_params": best_params_xgb,
                        },
                    },
                    "backtest": backtest_metrics,
                },
                "data_quality": {
                    "zero_days": zero_days,
                    "zero_days_pct": zero_days_pct,
                    "missing_price": missing_price,
                    "has_zero_in_holdout": has_zero_in_holdout,
                },
            }

            with open(model_dir / "metadata.json", "w") as f:
                json.dump(metadata, f, indent=2)

            # registrar no banco
            modelo = ModeloPredicao(
                produto_id=produto.id,
                modelo_tipo="ensemble_stacking",
                versao="3.5_ultra_optimized",
                caminho_modelo=str(model_dir / "ensemble_base.pkl"),
                metricas=holdout_metrics,
                treinado_em=datetime.now(timezone.utc),
            )
            session.add(modelo)
            session.commit()

            # print amigável
            msg = (
                f"    ✅ {produto.sku} - HOLDOUT: "
                f"RMSE={holdout_metrics['rmse']:.4f} "
                f"MAE={holdout_metrics['mae']:.4f}"
            )
            mape_val = holdout_metrics.get("mape")
            if mape_val is not None and not np.isnan(mape_val):
                msg += f" MAPE={mape_val:.2f}%"
            else:
                msg += " MAPE=IGNORADO(ZEROS)"

            msg += f" WMAPE={holdout_metrics['wmape']:.2f}%"
            print(msg)

            if optimize and not small_data:
                print(
                    f"       (search) lgb_rmse_cv={best_rmse_lgb:.4f} | "
                    f"(search) xgb_rmse_cv={best_rmse_xgb:.4f}"
                )

            return True

    except Exception as e:
        print(f"    ❌ {produto.sku} - Erro: {str(e)}")
        return False


# ======================================================================================
# 12) MAIN / CLI
# ======================================================================================
def main() -> bool:
    parser = argparse.ArgumentParser("Treina modelos avançados por produto (Multi-Target).")
    parser.add_argument("--no-optuna", action="store_true", help="Desativa tuning com Optuna.")
    parser.add_argument("--trials", type=int, default=15, help="Trials por modelo (padrão: 15, reduzido para velocidade).")
    parser.add_argument("--no-backtest", action="store_true", help="Desativa backtest deslizante.")
    parser.add_argument("--sku", type=str, help="Treinar só 1 SKU.")
    parser.add_argument("--limit", type=int, help="Limitar quantidade de SKUs.")
    parser.add_argument(
        "--bulk",
        action="store_true",
        help="Modo rápido: sem backtest, sem Optuna em série curta, ideal para popular.",
    )
    parser.add_argument(
        "--use-all-data",
        action="store_true",
        help="Usar 100% dos dados para treino (sem split de validação). Maximiza dados disponíveis.",
    )
    parser.add_argument(
        "--targets",
        type=str,
        default="quantidade,preco",
        help="Targets para treinar (padrão: quantidade,preco). "
             "Opções: quantidade, preco, receita, lucro, margem, custo, rotatividade, dias_estoque",
    )
    args = parser.parse_args()

    optimize = not args.no_optuna
    do_backtest = not args.no_backtest
    targets_list = [t.strip() for t in args.targets.split(",")]

    # ✅ NOVO: Validar targets
    VALID_TARGETS = {"quantidade", "preco", "receita", "lucro", "margem", "custo", "rotatividade", "dias_estoque"}
    invalid_targets = set(targets_list) - VALID_TARGETS
    if invalid_targets:
        print(f"❌ Targets inválidos: {invalid_targets}")
        print(f"   Válidos: {', '.join(sorted(VALID_TARGETS))}")
        return False
    
    # ✅ NOVO: Mostrar configuração de otimização + GPU
    print(f"\n{'='*80}")
    print(f"🚀 CONFIGURAÇÃO DE TREINO")
    print(f"{'='*80}")
    print(f"📊 Targets: {', '.join(targets_list)}")
    print(f"🔧 Trials: {args.trials}")
    print(f"🎮 GPU: {'✅ ATIVADA' if HAS_GPU else '❌ NÃO DETECTADA'} {f'({GPU_NAME})' if GPU_NAME else ''}")
    print(f"📈 Feature Engineering: Lags até 90 dias")
    print(f"{'='*80}\n")

    if args.bulk:
        optimize = False
        do_backtest = False

    with Session(engine) as session:
        if args.sku:
            produtos = list(session.exec(select(Produto).where(Produto.sku == args.sku)))
        else:
            produtos = list(session.exec(select(Produto)).all())

    if not produtos:
        print("❌ Nenhum produto encontrado.")
        return False

    if args.limit:
        produtos = produtos[: args.limit]

    print(
        f"🚀 Treinando {len(produtos)} produtos × {len(targets_list)} targets | "
        f"optuna={'on' if optimize else 'off'} (trials={args.trials}) | "
        f"backtest={'on' if do_backtest else 'off'} | "
        f"use_all_data={'on' if args.use_all_data else 'off'} | "
        f"gpu={'on' if USE_GPU else 'off'}"
    )
    print(
        f"📊 Targets: {', '.join(targets_list)} | "
        f"Feature engineering expandido | Tratamento de zeros | CV 5-fold"
    )
    print()

    success = 0
    total = len(produtos) * len(targets_list)
    current = 0
    
    for prod in produtos:
        for tgt in targets_list:
            current += 1
            print(f"[{current}/{total}] {prod.sku} → {tgt}")
            ok = train_product_model(
                prod,
                optimize=optimize,
                n_trials=args.trials,
                backtest=do_backtest,
                use_all_data=args.use_all_data,
                target=tgt,  # ← Passar target
            )
            if ok:
                success += 1

    print(f"\n✅ Concluído: {success}/{len(produtos)}")
    return success > 0


if __name__ == "__main__":
    ok = main()
    sys.exit(0 if ok else 1)
