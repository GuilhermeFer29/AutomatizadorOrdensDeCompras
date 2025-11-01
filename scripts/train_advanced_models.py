#!/usr/bin/env python3
"""
Treinamento Avançado de Modelos por Produto (v2.2)

Melhorias desta versão:
- Calendário diário forçado antes do feature engineering
- Guard-rails para Optuna (não afinar série curta)
- Stacking com OOF usando TimeSeriesSplit (mais estável)
- Silêncio de logs de LGB/XGB usando callbacks oficiais
- Modo --bulk para popular rápido
- Salvamento do dataset de treino por SKU
- Métricas de qualidade de dado no metadata

Requer:
- lightgbm >= 4.6  (early_stopping com callback)
- xgboost >= 3.1   (early_stopping_rounds como parâmetro)
- optuna >= 4.5    (study.optimize padrão)
- scikit-learn >= 1.7 (TimeSeriesSplit com n_splits)
"""

import sys
import argparse
import json
import pickle
import warnings
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Tuple, Optional, Any

import numpy as np
import pandas as pd
from sqlmodel import Session, select

from sklearn.preprocessing import RobustScaler
from sklearn.model_selection import TimeSeriesSplit
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.metrics import (
    mean_squared_error,
    mean_absolute_error,
)
from sklearn.linear_model import Ridge

import lightgbm as lgb
import xgboost as xgb
import optuna
from optuna.samplers import TPESampler
from optuna.pruners import MedianPruner

warnings.filterwarnings("ignore")

# --------------------------------------------------------
# DETECÇÃO DE GPU
# --------------------------------------------------------
import subprocess

def check_gpu_available():
    """Verifica GPU via nvidia-smi"""
    try:
        result = subprocess.run(['nvidia-smi', '--query-gpu=name', '--format=csv,noheader'], 
                              capture_output=True, text=True, timeout=5)
        if result.returncode == 0 and result.stdout.strip():
            return True, result.stdout.strip().split('\n')[0]
    except:
        pass
    return False, None

HAS_GPU, GPU_NAME = check_gpu_available()
GPU_DEVICE = 0

if HAS_GPU:
    print(f"🎮 GPU Disponível: True")
    print(f"   Device: {GPU_NAME}")
else:
    print(f"🎮 GPU Disponível: False (usando CPU)")

# --------------------------------------------------------
# IMPORTS DO PROJETO
# --------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.core.database import engine
from app.models.models import Produto, VendasHistoricas, PrecosHistoricos, ModeloPredicao

# --------------------------------------------------------
# CONSTANTES
# --------------------------------------------------------
MIN_SAMPLES = 90
FORECAST_HORIZON = 7
HOLDOUT_RATIO = 0.2
BACKTEST_SPLITS = 3
RANDOM_SEED = 42


# --------------------------------------------------------
# MÉTRICAS (com tratamento de zeros)
# --------------------------------------------------------
def mape_safe(y_true: np.ndarray, y_pred: np.ndarray, eps: float = 1.0) -> float:
    """
    MAPE seguro que ignora alvos muito pequenos (0, 1, 2...).
    Se todos os pontos são < eps, devolve NaN.
    
    Referência: https://otexts.com/fpp3/accuracy.html
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
    Weighted MAPE (WAPE) - não explode com zeros espalhados.
    Usado em supply chain e demand forecasting.
    
    Referência: https://en.wikipedia.org/wiki/Mean_absolute_percentage_error
    """
    y_true = np.asarray(y_true)
    y_pred = np.asarray(y_pred)
    
    num = np.sum(np.abs(y_true - y_pred))
    den = np.sum(np.abs(y_true)) + eps
    return float(num / den * 100.0)


def eval_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> Dict[str, float]:
    """Calcula métricas robustas para séries temporais com possíveis zeros."""
    mse = mean_squared_error(y_true, y_pred)
    rmse = np.sqrt(mse)
    mae = mean_absolute_error(y_true, y_pred)
    mape = mape_safe(y_true, y_pred, eps=1.0)
    wmape_val = wmape(y_true, y_pred)
    
    return {
        "rmse": float(rmse),
        "mae": float(mae),
        "mape": float(mape),
        "wmape": float(wmape_val),
    }


# --------------------------------------------------------
# DATAFRAME BASE (CALENDÁRIO DIÁRIO)
# --------------------------------------------------------
def build_base_dataframe(
    vendas: List[VendasHistoricas],
    precos: List[PrecosHistoricos],
) -> pd.DataFrame:
    """Normaliza vendas e preços para calendário diário antes das features."""
    if not vendas:
        raise ValueError("Sem vendas")
    
    # Agregar vendas por data (soma quantidade e receita)
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
        # Agregar preços por data (média)
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

    # preencher
    df["preco"] = df["preco"].ffill().bfill()
    df["quantidade"] = df["quantidade"].fillna(0)
    df["receita"] = df["receita"].fillna(0)

    df = df.reset_index()
    return df


# --------------------------------------------------------
# FEATURES
# --------------------------------------------------------
def create_time_series_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    # lags
    for lag in [1, 7, 14, 30]:
        df[f"lag_{lag}"] = df["quantidade"].shift(lag)

    # rolling
    for window in [7, 14, 30]:
        df[f"rolling_mean_{window}"] = df["quantidade"].rolling(window=window).mean()
        df[f"rolling_std_{window}"] = df["quantidade"].rolling(window=window).std()

    # ewm
    df["ewm_mean"] = df["quantidade"].ewm(span=14).mean()

    # calendário
    df["day_of_week"] = df["data_venda"].dt.dayofweek
    df["day_of_month"] = df["data_venda"].dt.day
    df["month"] = df["data_venda"].dt.month
    df["quarter"] = df["data_venda"].dt.quarter
    df["is_weekend"] = (df["day_of_week"] >= 5).astype(int)

    # tendência
    df["trend"] = np.arange(len(df))

    # preço
    df["preco_lag_1"] = df["preco"].shift(1)
    df["preco_mean_7"] = df["preco"].rolling(window=7).mean()
    df["preco_volatility"] = df["preco"].rolling(window=7).std()

    df = df.dropna()
    return df


def prepare_training_data(
    df: pd.DataFrame, forecast_horizon: int = FORECAST_HORIZON
) -> Tuple[np.ndarray, np.ndarray, List[str]]:
    features_df = df.drop(columns=["quantidade", "data_venda", "preco", "receita"], errors="ignore")

    y = df["quantidade"].shift(-forecast_horizon).dropna()
    X = features_df.iloc[:-forecast_horizon]

    min_len = min(len(X), len(y))
    X = X.iloc[:min_len]
    y = y.iloc[:min_len]

    return X.values, y.values, list(X.columns)


# --------------------------------------------------------
# OPTUNA OBJECTIVES
# --------------------------------------------------------
def objective_lgb(trial: optuna.Trial, X_train: np.ndarray, y_train: np.ndarray) -> float:
    params = {
        "num_leaves": trial.suggest_int("num_leaves", 20, 150),
        "max_depth": trial.suggest_int("max_depth", 3, 15),
        "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.3, log=True),
        "feature_fraction": trial.suggest_float("feature_fraction", 0.5, 1.0),
        "bagging_fraction": trial.suggest_float("bagging_fraction", 0.5, 1.0),
        "bagging_freq": trial.suggest_int("bagging_freq", 1, 10),
        "lambda_l1": trial.suggest_float("lambda_l1", 0.0, 10.0),
        "lambda_l2": trial.suggest_float("lambda_l2", 0.0, 10.0),
        "min_data_in_leaf": trial.suggest_int("min_data_in_leaf", 5, 60),
    }

    tscv = TimeSeriesSplit(n_splits=3)
    scores = []

    for tr_idx, val_idx in tscv.split(X_train):
        X_tr, X_val = X_train[tr_idx], X_train[val_idx]
        y_tr, y_val = y_train[tr_idx], y_train[val_idx]

        # LightGBM com GPU se disponível (CUDA 13.0 + RTX 2060)
        lgb_params = params.copy()
        if HAS_GPU:
            lgb_params["device_type"] = "cuda"
            lgb_params["gpu_device_id"] = GPU_DEVICE
            lgb_params["max_bin"] = 63  # Recomendado para GPU
        
        model = lgb.LGBMRegressor(
            **lgb_params,
            n_estimators=200,
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
        metrics = eval_metrics(y_val, y_pred)
        scores.append(metrics["rmse"])

    return float(np.mean(scores))


def objective_xgb(trial: optuna.Trial, X_train: np.ndarray, y_train: np.ndarray) -> float:
    params = {
        "max_depth": trial.suggest_int("max_depth", 3, 15),
        "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.3, log=True),
        "subsample": trial.suggest_float("subsample", 0.5, 1.0),
        "colsample_bytree": trial.suggest_float("colsample_bytree", 0.5, 1.0),
        "reg_alpha": trial.suggest_float("reg_alpha", 0.0, 10.0),
        "reg_lambda": trial.suggest_float("reg_lambda", 0.0, 10.0),
        "min_child_weight": trial.suggest_int("min_child_weight", 1, 10),
    }

    tscv = TimeSeriesSplit(n_splits=3)
    scores = []

    for tr_idx, val_idx in tscv.split(X_train):
        X_tr, X_val = X_train[tr_idx], X_train[val_idx]
        y_tr, y_val = y_train[tr_idx], y_train[val_idx]

        # XGBoost com GPU se disponível (conforme doc oficial)
        # device: "cuda" ou "cuda:0" para GPU NVIDIA
        # tree_method: "hist" é obrigatório com GPU
        xgb_params = params.copy()
        xgb_params["tree_method"] = "hist"
        if HAS_GPU:
            xgb_params["device"] = "cuda"
        
        model = xgb.XGBRegressor(
            **xgb_params,
            n_estimators=200,
            random_state=RANDOM_SEED,
            verbosity=0,
            early_stopping_rounds=50,
        )
        model.fit(
            X_tr,
            y_tr,
            eval_set=[(X_val, y_val)],
            verbose=False,
        )
        y_pred = model.predict(X_val)
        metrics = eval_metrics(y_val, y_pred)
        scores.append(metrics["rmse"])

    return float(np.mean(scores))


# --------------------------------------------------------
# STACKING COM OOF (TimeSeriesSplit)
# --------------------------------------------------------
def build_stacking_with_oof(
    X_train: np.ndarray,
    y_train: np.ndarray,
    X_val: np.ndarray,
    y_val: np.ndarray,
    best_params_lgb: Dict[str, Any],
    best_params_xgb: Dict[str, Any],
) -> Dict[str, Any]:
    # Preparar parâmetros com GPU se disponível
    lgb_params_final = best_params_lgb.copy()
    xgb_params_final = best_params_xgb.copy()
    
    # LightGBM com GPU (CUDA 13.0)
    if HAS_GPU:
        lgb_params_final["device_type"] = "cuda"
        lgb_params_final["gpu_device_id"] = GPU_DEVICE
        lgb_params_final["max_bin"] = 63
    
    # XGBoost com GPU
    xgb_params_final["tree_method"] = "hist"
    if HAS_GPU:
        xgb_params_final["device"] = "cuda"
    
    base_models = {
        "lgb": lgb.LGBMRegressor(
            **lgb_params_final,
            n_estimators=300,
            random_state=RANDOM_SEED,
            verbose=-1,
        ),
        "xgb": xgb.XGBRegressor(
            **xgb_params_final,
            n_estimators=300,
            random_state=RANDOM_SEED,
            verbosity=0,
        ),
        "rf": RandomForestRegressor(
            n_estimators=200,
            max_depth=15,
            random_state=RANDOM_SEED,
            n_jobs=-1,
        ),
        "gb": GradientBoostingRegressor(
            n_estimators=200,
            max_depth=5,
            learning_rate=0.1,
            random_state=RANDOM_SEED,
        ),
    }

    # OOF com 3 splits
    tscv = TimeSeriesSplit(n_splits=3)
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


# --------------------------------------------------------
# BACKTEST
# --------------------------------------------------------
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
    results = []
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


# --------------------------------------------------------
# TREINO POR PRODUTO
# --------------------------------------------------------
def train_product_model(
    produto: Produto,
    optimize: bool = True,
    n_trials: int = 20,
    backtest: bool = True,
) -> bool:
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

            # base diária
            df = build_base_dataframe(vendas, precos)
            df = create_time_series_features(df)
            if len(df) < MIN_SAMPLES:
                print(f"    ⚠️ {produto.sku} - features insuficientes ({len(df)}/{MIN_SAMPLES})")
                return False

            # qualidade de dado
            zero_days = int((df["quantidade"] == 0).sum())
            zero_days_pct = zero_days / len(df)
            missing_price = int(df["preco"].isna().sum())

            # prepara X, y
            X, y, feature_names = prepare_training_data(df)

            # split temporal holdout
            split_idx = int(len(X) * (1 - HOLDOUT_RATIO))
            X_train, X_val = X[:split_idx], X[split_idx:]
            y_train, y_val = y[:split_idx], y[split_idx:]
            
            # marca se holdout tem zeros
            has_zero_in_holdout = bool((y_val == 0).any())

            scaler = RobustScaler()
            X_train_scaled = scaler.fit_transform(X_train)
            X_val_scaled = scaler.transform(X_val)

            # guard-rails optuna
            small_data = len(X_train_scaled) < 120
            if optimize and not small_data:
                print(f"    🔧 {produto.sku} - Otimizando hiperparâmetros (n_trials={n_trials})...")
                # LGB
                study_lgb = optuna.create_study(
                    sampler=TPESampler(seed=RANDOM_SEED),
                    pruner=MedianPruner(),
                    direction="minimize",
                )
                study_lgb.optimize(
                    lambda trial: objective_lgb(trial, X_train_scaled, y_train),
                    n_trials=n_trials,
                    show_progress_bar=False,
                )
                best_params_lgb = study_lgb.best_params
                best_rmse_lgb = study_lgb.best_value

                # XGB
                study_xgb = optuna.create_study(
                    sampler=TPESampler(seed=RANDOM_SEED),
                    pruner=MedianPruner(),
                    direction="minimize",
                )
                study_xgb.optimize(
                    lambda trial: objective_xgb(trial, X_train_scaled, y_train),
                    n_trials=n_trials,
                    show_progress_bar=False,
                )
                best_params_xgb = study_xgb.best_params
                best_rmse_xgb = study_xgb.best_value
            else:
                print(f"    ℹ️ {produto.sku} - pouco dado ou optimize off, usando defaults.")
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
                    "tree_method": "hist",
                }
                best_rmse_xgb = None

            # stacking
            stacking_result = build_stacking_with_oof(
                X_train_scaled,
                y_train,
                X_val_scaled,
                y_val,
                best_params_lgb,
                best_params_xgb,
            )
            holdout_metrics = stacking_result["holdout_metrics"]

            # backtest
            backtest_metrics = []
            if backtest:
                backtest_metrics = sliding_backtest(
                    X,
                    y,
                    scaler,
                    best_params_lgb=best_params_lgb,
                    n_splits=BACKTEST_SPLITS,
                )

            # persistência
            model_dir = PROJECT_ROOT / "model" / produto.sku
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

            metadata = {
                "produto_id": produto.id,
                "sku": produto.sku,
                "modelo_tipo": "ensemble_stacking",
                "versao": "2.2_advanced",
                "treinado_em": datetime.now(timezone.utc).isoformat(),
                "amostras_totais": int(len(X)),
                "amostras_treino": int(len(X_train)),
                "amostras_validacao": int(len(X_val)),
                "forecast_horizon": FORECAST_HORIZON,
                "holdout_ratio": HOLDOUT_RATIO,
                "feature_names": feature_names,
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
                    "zero_days_pct": float(zero_days_pct),
                    "missing_price": missing_price,
                    "has_zero_in_holdout": has_zero_in_holdout,
                },
            }

            with open(model_dir / "metadata.json", "w") as f:
                json.dump(metadata, f, indent=2)

            # registra no banco
            modelo = ModeloPredicao(
                produto_id=produto.id,
                modelo_tipo="ensemble_stacking",
                versao="2.2_advanced",
                caminho_modelo=str(model_dir / "ensemble_base.pkl"),
                metricas=holdout_metrics,
                treinado_em=datetime.now(timezone.utc),
            )
            session.add(modelo)
            session.commit()

            # Print com tratamento de MAPE NaN
            msg = f"    ✅ {produto.sku} - HOLDOUT: RMSE={holdout_metrics['rmse']:.4f} MAE={holdout_metrics['mae']:.4f}"
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


# --------------------------------------------------------
# MAIN / CLI
# --------------------------------------------------------
def main() -> bool:
    parser = argparse.ArgumentParser("Treina modelos avançados por produto.")
    parser.add_argument("--no-optuna", action="store_true", help="Desativa tuning com Optuna.")
    parser.add_argument("--trials", type=int, default=20, help="Trials por modelo.")
    parser.add_argument("--no-backtest", action="store_true", help="Desativa backtest deslizante.")
    parser.add_argument("--sku", type=str, help="Treinar só 1 SKU.")
    parser.add_argument("--limit", type=int, help="Limitar quantidade de SKUs.")
    parser.add_argument("--bulk", action="store_true", help="Modo rápido: sem backtest, poucos trials, sem Optuna em série curta.")
    args = parser.parse_args()

    optimize = not args.no_optuna
    do_backtest = not args.no_backtest

    if args.bulk:
        optimize = False  # modo popular
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
        f"🚀 Treinando {len(produtos)} produtos | "
        f"optuna={'on' if optimize else 'off'} | backtest={'on' if do_backtest else 'off'}"
    )

    success = 0
    for idx, prod in enumerate(produtos, 1):
        print(f"[{idx}/{len(produtos)}] {prod.sku}")
        ok = train_product_model(
            prod,
            optimize=optimize,
            n_trials=args.trials,
            backtest=do_backtest,
        )
        if ok:
            success += 1

    print(f"\n✅ Concluído: {success}/{len(produtos)}")
    return success > 0


if __name__ == "__main__":
    ok = main()
    sys.exit(0 if ok else 1)
