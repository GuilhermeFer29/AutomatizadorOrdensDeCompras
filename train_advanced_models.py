#!/usr/bin/env python3
"""
Treinamento Avançado de Modelos com Melhores Práticas (v2.1)

Objetivo:
- Ter métricas comparáveis entre estágios (search vs holdout vs backtest)
- Reduzir otimismo do stacking
- Facilitar debug de cada SKU
- Permitir rodar com/sem Optuna via CLI

Principais blocos:
1. Extração e feature engineering
2. Preparação (target deslocado)
3. Split temporal + scaler só no train
4. (Opcional) Optuna para LGB e XGB em cima do TRAIN
5. Treino dos 4 modelos base
6. Stacking com OOF simples
7. Avaliação: holdout + (opcional) backtest
8. Persistência (modelos, scaler, metadata)
"""

import sys
import argparse
import json
import pickle
import warnings
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, List, Tuple, Optional

import numpy as np
import pandas as pd
from sqlmodel import Session, select

# ML
from sklearn.preprocessing import RobustScaler
from sklearn.model_selection import TimeSeriesSplit
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.metrics import (
    mean_squared_error,
    mean_absolute_error,
    mean_absolute_percentage_error,
)
from sklearn.linear_model import Ridge

# Compatibilidade sklearn 1.4+: root_mean_squared_error
try:
    from sklearn.metrics import root_mean_squared_error
    HAS_RMSE = True
except ImportError:
    HAS_RMSE = False

import lightgbm as lgb
import xgboost as xgb
import optuna
from optuna.samplers import TPESampler
from optuna.pruners import MedianPruner

warnings.filterwarnings("ignore")

# =====================================================================
# DETECÇÃO DE GPU (sem torch - mais leve)
# =====================================================================
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

# =====================================================================
# IMPORTS DO PROJETO
# =====================================================================
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.core.database import engine
from app.models.models import Produto, VendasHistoricas, PrecosHistoricos, ModeloPredicao

# =====================================================================
# CONFIGURAÇÕES GERAIS
# =====================================================================
MIN_SAMPLES = 90            # Mínimo de registros para considerar o produto
LOOKBACK_WINDOW = 30        # Janela de lags
FORECAST_HORIZON = 7        # Quantos dias à frente vamos prever
HOLDOUT_RATIO = 0.2         # 20% final para validação
BACKTEST_SPLITS = 3         # Quantos cortes de backtest fazer no histórico

RANDOM_SEED = 42

# =====================================================================
# MÉTRICAS CONSISTENTES
# =====================================================================

def eval_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> Dict[str, float]:
    """Métrica única para todo o pipeline. MAPE sempre em %."""
    # sklearn 1.4+: usar root_mean_squared_error (squared foi deprecado em 1.4)
    # Fallback para versões antigas: np.sqrt(mse)
    if HAS_RMSE:
        rmse = root_mean_squared_error(y_true, y_pred)
    else:
        mse = mean_squared_error(y_true, y_pred)
        rmse = np.sqrt(mse)
    
    mae = mean_absolute_error(y_true, y_pred)
    mape = mean_absolute_percentage_error(y_true, y_pred) * 100  # %
    return {"rmse": float(rmse), "mae": float(mae), "mape": float(mape)}


# =====================================================================
# FEATURE ENGINEERING
# =====================================================================

def create_time_series_features(df: pd.DataFrame, lookback: int = LOOKBACK_WINDOW) -> pd.DataFrame:
    df = df.copy()

    # Lags principais
    for lag in [1, 7, 14, 30]:
        df[f"lag_{lag}"] = df["quantidade"].shift(lag)

    # Rolling
    for window in [7, 14, 30]:
        df[f"rolling_mean_{window}"] = df["quantidade"].rolling(window=window).mean()
        df[f"rolling_std_{window}"] = df["quantidade"].rolling(window=window).std()

    # EWM
    df["ewm_mean"] = df["quantidade"].ewm(span=14).mean()

    # Calendário
    df["day_of_week"] = df["data_venda"].dt.dayofweek
    df["day_of_month"] = df["data_venda"].dt.day
    df["month"] = df["data_venda"].dt.month
    df["quarter"] = df["data_venda"].dt.quarter
    df["is_weekend"] = (df["day_of_week"] >= 5).astype(int)

    # Tendência
    df["trend"] = np.arange(len(df))

    # Preço e estatísticas
    df["preco_lag_1"] = df["preco"].shift(1)
    df["preco_mean_7"] = df["preco"].rolling(window=7).mean()
    df["preco_volatility"] = df["preco"].rolling(window=7).std()

    # Limpa NaNs gerados por lags/rollings
    df = df.dropna()

    return df


def prepare_training_data(
    df: pd.DataFrame, forecast_horizon: int = FORECAST_HORIZON
) -> Tuple[np.ndarray, np.ndarray, List[str]]:
    """
    Prepara X, y e mantém nomes de colunas (útil pra debug).
    """
    feature_df = df.drop(columns=["quantidade", "data_venda", "preco", "receita"], errors="ignore")

    # Target deslocado
    y = df["quantidade"].shift(-forecast_horizon).dropna()
    X = feature_df.iloc[:-forecast_horizon]

    min_len = min(len(X), len(y))
    X = X.iloc[:min_len]
    y = y.iloc[:min_len]

    return X.values, y.values, list(X.columns)


# =====================================================================
# OBJETIVOS OPTUNA
# =====================================================================

def objective_lgb(trial: optuna.Trial, X_train: np.ndarray, y_train: np.ndarray) -> float:
    params = {
        "num_leaves": trial.suggest_int("num_leaves", 20, 150),
        "max_depth": trial.suggest_int("max_depth", 3, 15),
        "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.3, log=True),
        "feature_fraction": trial.suggest_float("feature_fraction", 0.5, 1.0),
        "bagging_fraction": trial.suggest_float("bagging_fraction", 0.5, 1.0),
        "bagging_freq": trial.suggest_int("bagging_freq", 1, 10),
        "lambda_l1": trial.suggest_float("lambda_l1", 0, 10),
        "lambda_l2": trial.suggest_float("lambda_l2", 0, 10),
        "min_data_in_leaf": trial.suggest_int("min_data_in_leaf", 5, 50),
    }

    tscv = TimeSeriesSplit(n_splits=3)
    scores = []

    for tr_idx, val_idx in tscv.split(X_train):
        X_tr, X_val = X_train[tr_idx], X_train[val_idx]
        y_tr, y_val = y_train[tr_idx], y_train[val_idx]

        model = lgb.LGBMRegressor(
            **params,
            n_estimators=200,
            random_state=RANDOM_SEED,
            verbose=-1,
        )
        model.fit(
            X_tr,
            y_tr,
            eval_set=[(X_val, y_val)],
            callbacks=[lgb.early_stopping(stopping_rounds=50)],
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
        "reg_alpha": trial.suggest_float("reg_alpha", 0, 10),
        "reg_lambda": trial.suggest_float("reg_lambda", 0, 10),
        "min_child_weight": trial.suggest_int("min_child_weight", 1, 10),
    }

    tscv = TimeSeriesSplit(n_splits=3)
    scores = []

    for tr_idx, val_idx in tscv.split(X_train):
        X_tr, X_val = X_train[tr_idx], X_train[val_idx]
        y_tr, y_val = y_train[tr_idx], y_train[val_idx]

        model = xgb.XGBRegressor(
            **params,
            n_estimators=200,
            random_state=RANDOM_SEED,
            verbosity=0,
            early_stopping_rounds=50,  # XGBoost 2.0+: usar parâmetro direto
        )
        # XGBoost 2.0+: early_stopping_rounds é parâmetro do modelo, não callback
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


# =====================================================================
# STACKING (com OOF simples)
# =====================================================================

def build_stacking_with_oof(
    X_train: np.ndarray,
    y_train: np.ndarray,
    X_val: np.ndarray,
    y_val: np.ndarray,
    best_params_lgb: Dict,
    best_params_xgb: Dict,
) -> Dict:
    """
    Faz o stacking em 2 níveis:
    - nível 1: 4 modelos (lgb, xgb, rf, gb)
    - nível 2: ridge
    Com geração de OOF para o treino (1 split simples).
    """
    # Modelos base
    base_models = {
        "lgb": lgb.LGBMRegressor(
            **best_params_lgb,
            n_estimators=300,
            random_state=RANDOM_SEED,
            verbose=-1,
        ),
        "xgb": xgb.XGBRegressor(
            **best_params_xgb,
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

    # OOF: vamos fazer 1 split temporal dentro do train
    inner_split = int(len(X_train) * 0.8)
    X_tr_inner, X_oof = X_train[:inner_split], X_train[inner_split:]
    y_tr_inner, y_oof = y_train[:inner_split], y_train[inner_split:]

    # Treina modelos base no pedaço maior
    for m in base_models.values():
        m.fit(X_tr_inner, y_tr_inner)

    # Gera OOF pro pedaço menor
    meta_train = np.column_stack([m.predict(X_oof) for m in base_models.values()])
    meta_val = np.column_stack([m.predict(X_val) for m in base_models.values()])

    # Meta-learner
    meta_learner = Ridge(alpha=1.0)
    meta_learner.fit(meta_train, y_oof)

    # Avaliação no holdout real
    y_pred_val = meta_learner.predict(meta_val)
    holdout_metrics = eval_metrics(y_val, y_pred_val)

    return {
        "base_models": base_models,
        "meta_learner": meta_learner,
        "holdout_metrics": holdout_metrics,
    }


# =====================================================================
# BACKTEST DESLIZANTE (opcional)
# =====================================================================

def sliding_backtest(
    X: np.ndarray,
    y: np.ndarray,
    scaler: RobustScaler,
    best_params_lgb: Dict,
    best_params_xgb: Dict,
    n_splits: int = BACKTEST_SPLITS,
) -> List[Dict[str, float]]:
    """
    Faz um backtest rápido: em cada split treina LGB com os melhores params
    e avalia no trecho seguinte. Não faz stacking aqui pra ficar rápido.
    """
    if len(X) < 60:  # muito curto
        return []

    tscv = TimeSeriesSplit(n_splits=n_splits)
    results = []
    for tr_idx, val_idx in tscv.split(X):
        X_tr, X_val = X[tr_idx], X[val_idx]
        y_tr, y_val = y[tr_idx], y[val_idx]

        # reescala dentro do split usando o scaler já fitado na pipeline principal
        X_tr = scaler.transform(X_tr)
        X_val = scaler.transform(X_val)

        model = lgb.LGBMRegressor(
            **best_params_lgb,
            n_estimators=200,
            random_state=RANDOM_SEED,
            verbose=-1,
        )
        model.fit(X_tr, y_tr)
        y_pred = model.predict(X_val)
        metrics = eval_metrics(y_val, y_pred)
        results.append(metrics)

    return results


# =====================================================================
# TREINO POR PRODUTO
# =====================================================================

def train_product_model(
    produto: Produto,
    optimize: bool = True,
    n_trials: int = 20,
    backtest: bool = True,
) -> bool:
    try:
        with Session(engine) as session:
            # -----------------------------------------------------------------
            # 1) Carregar dados
            # -----------------------------------------------------------------
            vendas = session.exec(
                select(VendasHistoricas)
                .where(VendasHistoricas.produto_id == produto.id)
                .order_by(VendasHistoricas.data_venda)
            ).all()

            if len(vendas) < MIN_SAMPLES:
                print(f"    ⚠️  {produto.sku} - Dados insuficientes ({len(vendas)}/{MIN_SAMPLES})")
                return False

            precos = session.exec(
                select(PrecosHistoricos)
                .where(PrecosHistoricos.produto_id == produto.id)
                .order_by(PrecosHistoricos.coletado_em)
            ).all()

            df = pd.DataFrame(
                {
                    "data_venda": [v.data_venda for v in vendas],
                    "quantidade": [v.quantidade for v in vendas],
                    "receita": [float(v.receita) for v in vendas],
                }
            )

            df_precos = pd.DataFrame(
                {
                    "data_venda": [p.coletado_em for p in precos],
                    "preco": [float(p.preco) for p in precos],
                }
            )

            df = df.merge(df_precos, on="data_venda", how="left")
            df["preco"] = df["preco"].fillna(method="ffill").fillna(method="bfill")

            # -----------------------------------------------------------------
            # 2) Features
            # -----------------------------------------------------------------
            df = create_time_series_features(df)
            if len(df) < MIN_SAMPLES:
                print(f"    ⚠️  {produto.sku} - Features insuficientes após engenharia")
                return False

            # -----------------------------------------------------------------
            # 3) Preparar X, y
            # -----------------------------------------------------------------
            X, y, feature_names = prepare_training_data(df)

            # -----------------------------------------------------------------
            # 4) Split temporal (holdout real = últimos 20%)
            # -----------------------------------------------------------------
            split_idx = int(len(X) * (1 - HOLDOUT_RATIO))
            X_train, X_val = X[:split_idx], X[split_idx:]
            y_train, y_val = y[:split_idx], y[split_idx:]

            # -----------------------------------------------------------------
            # 5) Scaler fitado só no train
            # -----------------------------------------------------------------
            scaler = RobustScaler()
            X_train_scaled = scaler.fit_transform(X_train)
            X_val_scaled = scaler.transform(X_val)

            # -----------------------------------------------------------------
            # 6) (Opcional) Optuna
            # -----------------------------------------------------------------
            if optimize:
                print(f"    🔧 {produto.sku} - Otimizando hiperparâmetros (n_trials={n_trials}) ...")
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
                # defaults razoáveis
                print(f"    ℹ️  {produto.sku} - Otimização desativada, usando hyperparams padrão.")
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

            # -----------------------------------------------------------------
            # 7) Stacking (com OOF) + métrica de holdout
            # -----------------------------------------------------------------
            stacking_result = build_stacking_with_oof(
                X_train_scaled,
                y_train,
                X_val_scaled,
                y_val,
                best_params_lgb,
                best_params_xgb,
            )
            holdout_metrics = stacking_result["holdout_metrics"]

            # -----------------------------------------------------------------
            # 8) (Opcional) Backtest
            # -----------------------------------------------------------------
            backtest_metrics = []
            if backtest:
                backtest_metrics = sliding_backtest(
                    X,
                    y,
                    scaler,
                    best_params_lgb=best_params_lgb,
                    best_params_xgb=best_params_xgb,
                    n_splits=BACKTEST_SPLITS,
                )

            # -----------------------------------------------------------------
            # 9) Persistência
            # -----------------------------------------------------------------
            model_dir = PROJECT_ROOT / "model" / produto.sku
            model_dir.mkdir(parents=True, exist_ok=True)

            # salva modelos base
            with open(model_dir / "ensemble_base.pkl", "wb") as f:
                pickle.dump(stacking_result["base_models"], f)

            # salva meta-learner
            with open(model_dir / "meta_learner.pkl", "wb") as f:
                pickle.dump(stacking_result["meta_learner"], f)

            # salva scaler
            with open(model_dir / "scaler.pkl", "wb") as f:
                pickle.dump(scaler, f)

            # metadata rica
            metadata = {
                "produto_id": produto.id,
                "sku": produto.sku,
                "modelo_tipo": "ensemble_stacking",
                "versao": "2.1_advanced",
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
            }

            with open(model_dir / "metadata.json", "w") as f:
                json.dump(metadata, f, indent=2)

            # registrar no banco
            modelo = ModeloPredicao(
                produto_id=produto.id,
                modelo_tipo="ensemble_stacking",
                versao="2.1_advanced",
                caminho_modelo=str(model_dir / "ensemble_base.pkl"),
                metricas=holdout_metrics,
                treinado_em=datetime.now(timezone.utc),
            )
            session.add(modelo)
            session.commit()

            print(
                f"    ✅ {produto.sku} - HOLDOUT: RMSE={holdout_metrics['rmse']:.4f} "
                f"MAE={holdout_metrics['mae']:.4f} MAPE={holdout_metrics['mape']:.2f}%"
            )
            if optimize:
                print(
                    f"       (search) lgb_rmse_cv={best_rmse_lgb:.4f} | "
                    f"(search) xgb_rmse_cv={best_rmse_xgb:.4f}"
                )

            return True

    except Exception as e:
        print(f"    ❌ {produto.sku} - Erro: {str(e)}")
        return False


# =====================================================================
# CLI / MAIN
# =====================================================================

def main():
    parser = argparse.ArgumentParser(description="Treina modelos avançados por produto.")
    parser.add_argument("--no-optuna", action="store_true", help="Desativa tuning com Optuna.")
    parser.add_argument("--trials", type=int, default=20, help="Qtd. de trials do Optuna.")
    parser.add_argument("--no-backtest", action="store_true", help="Desativa backtest deslizante.")
    parser.add_argument("--sku", type=str, help="Treina apenas um SKU.")
    parser.add_argument("--limit", type=int, help="Limita número de produtos a treinar.")
    args = parser.parse_args()

    print(
        """
╔════════════════════════════════════════════════════════════════════════╗
║     🚀 TREINAMENTO AVANÇADO DE MODELOS (v2.1)                          ║
║     • Feature Engineering Avançado                                     ║
║     • Ensemble Stacking (OOF)                                          ║
║     • Validação Temporal / Holdout                                     ║
║     • Hyperparameter Tuning com Optuna (opcional)                      ║
║     • Backtest deslizante (opcional)                                   ║
╚════════════════════════════════════════════════════════════════════════╝
"""
    )

    optimize = not args.no_optuna
    do_backtest = not args.no_backtest

    with Session(engine) as session:
        if args.sku:
            produtos = list(session.exec(select(Produto).where(Produto.sku == args.sku)))
        else:
            produtos = list(session.exec(select(Produto)).all())
    
    # Aplicar limite se especificado
    if args.limit:
        produtos = produtos[:args.limit]

    if not produtos:
        print("❌ Nenhum produto encontrado.")
        return False

    print(f"📦 Treinando {len(produtos)} modelos...\n")

    success_count = 0
    for idx, produto in enumerate(produtos, 1):
        print(f"[{idx}/{len(produtos)}] {produto.sku}")
        ok = train_product_model(
            produto,
            optimize=optimize,
            n_trials=args.trials,
            backtest=do_backtest,
        )
        if ok:
            success_count += 1

    print(f"\n✅ Treinamento concluído: {success_count}/{len(produtos)} modelos")
    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
