"""Treinamento global de preços com LightGBM e previsões multi-produto."""

from __future__ import annotations

import json
import os
from collections import deque
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional

import joblib
import numpy as np
import pandas as pd
import structlog
from lightgbm import LGBMRegressor, early_stopping
from sqlmodel import Session, select

from app.core.config import ROOT_DIR
from app.core.database import engine
from app.models.models import ModeloGlobal, PrecosHistoricos, Produto

LOGGER = structlog.get_logger(__name__)

MODELS_DIR = ROOT_DIR / "models"
DEFAULT_MODEL_PATH = MODELS_DIR / "global_lgbm_model.pkl"
METADATA_PATH = MODELS_DIR / "global_lgbm_metadata.json"

MINIMUM_HISTORY_POINTS = 120
HOLDOUT_DAYS = 30

for directory in (MODELS_DIR,):
    directory.mkdir(parents=True, exist_ok=True)


class InsufficientHistoryError(RuntimeError):
    """Erro lançado quando o histórico não é suficiente para treinar ou prever."""


def _load_price_history(session: Session) -> pd.DataFrame:
    registros = list(
        session.exec(
            select(PrecosHistoricos, Produto)
            .join(Produto, PrecosHistoricos.produto_id == Produto.id)
            .order_by(PrecosHistoricos.produto_id, PrecosHistoricos.coletado_em)
        )
    )

    if not registros:
        raise InsufficientHistoryError("Nenhum histórico de preços foi encontrado.")

    rows: List[Dict[str, object]] = []
    for preco, produto in registros:
        coleta = preco.coletado_em
        if coleta.tzinfo is None:
            coleta = coleta.replace(tzinfo=timezone.utc)
        coleta = coleta.astimezone(timezone.utc).replace(tzinfo=None)

        rows.append(
            {
                "produto_id": produto.id,
                "sku": produto.sku,
                "ds": coleta,
                "price": float(preco.preco),
            }
        )

    history_df = pd.DataFrame(rows)

    # Lida com timestamps duplicados para o mesmo produto, tirando a média dos preços do dia.
    history_df = history_df.groupby(["produto_id", "sku", "ds"]).agg(price=("price", "mean")).reset_index()

    grouped = history_df.groupby("produto_id")
    enough_data = grouped.size() >= MINIMUM_HISTORY_POINTS
    valid_ids = enough_data[enough_data].index.tolist()
    if not valid_ids:
        raise InsufficientHistoryError(
            f"Histórico insuficiente. Pelo menos {MINIMUM_HISTORY_POINTS} registros por produto são necessários."
        )

    filtered = history_df[history_df["produto_id"].isin(valid_ids)].copy()
    filtered.sort_values(["produto_id", "ds"], inplace=True)
    return filtered


def _create_feature_rich_dataframe(session: Session) -> pd.DataFrame:
    history = _load_price_history(session)

    def _expand_product(df: pd.DataFrame) -> pd.DataFrame:
        df = df.set_index("ds").asfreq("D")
        df["sku"] = df["sku"].ffill()
        df["price"] = df["price"].interpolate(method="time").ffill().bfill()
        df["produto_id"] = df["produto_id"].ffill()
        df.reset_index(inplace=True)
        df.rename(columns={"index": "ds"}, inplace=True)
        return df

    expanded = history.groupby("produto_id", group_keys=False).apply(_expand_product)

    expanded["day_of_week"] = expanded["ds"].dt.dayofweek
    expanded["week_of_year"] = expanded["ds"].dt.isocalendar().week.astype(int)
    expanded["month"] = expanded["ds"].dt.month

    for lag in (1, 7, 14):
        expanded[f"lag_{lag}"] = expanded.groupby("produto_id")["price"].shift(lag)

    for window in (7, 30):
        expanded[f"rolling_mean_{window}"] = (
            expanded.groupby("produto_id")["price"].rolling(window).mean().reset_index(level=0, drop=True)
        )
        expanded[f"rolling_std_{window}"] = (
            expanded.groupby("produto_id")["price"].rolling(window).std().reset_index(level=0, drop=True)
        )

    expanded.dropna(inplace=True)

    expanded["produto_id"] = expanded["produto_id"].astype("category")

    feature_columns = [
        "produto_id",
        "day_of_week",
        "week_of_year",
        "month",
        "lag_1",
        "lag_7",
        "lag_14",
        "rolling_mean_7",
        "rolling_std_7",
        "rolling_mean_30",
        "rolling_std_30",
    ]

    expanded.rename(columns={"price": "target"}, inplace=True)
    expanded = expanded.sort_values("ds")

    expanded[feature_columns] = expanded[feature_columns].astype({"produto_id": "category"})
    expanded.reset_index(drop=True, inplace=True)

    expanded.attrs["feature_columns"] = feature_columns
    return expanded


def _save_metadata(metrics: Dict[str, float], *, version: str, model_path: Path) -> None:
    payload = {
        "model_type": "lightgbm_global",
        "version": version,
        "model_path": str(model_path.relative_to(ROOT_DIR)) if model_path.is_absolute() else str(model_path),
        "metrics": metrics,
        "trained_at": datetime.now(timezone.utc).isoformat(),
    }
    METADATA_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    with Session(engine) as session:
        registro = ModeloGlobal(
            modelo_tipo="lightgbm_global",
            versao=version,
            holdout_dias=HOLDOUT_DAYS,
            caminho_modelo=payload["model_path"],
            caminho_relatorio="",
            metricas=metrics,
            treinado_em=datetime.now(timezone.utc),
        )
        session.add(registro)
        session.commit()


def train_global_lgbm_model() -> Dict[str, float]:
    """Treina o modelo global LightGBM e retorna as métricas de validação."""

    LOGGER.info("ml.training.lgbm.start")
    with Session(engine) as session:
        dataset = _create_feature_rich_dataframe(session)

    feature_columns: List[str] = dataset.attrs["feature_columns"]
    categorical_features = ["produto_id"]

    dataset["produto_id"] = dataset["produto_id"].cat.codes.astype(int)

    dataset = dataset.sort_values(["ds", "produto_id"])

    holdout_cutoff = dataset["ds"].max() - timedelta(days=HOLDOUT_DAYS)
    train_df = dataset[dataset["ds"] <= holdout_cutoff].copy()
    valid_df = dataset[dataset["ds"] > holdout_cutoff].copy()

    if train_df.empty or valid_df.empty:
        raise InsufficientHistoryError("Não foi possível separar janela de validação temporal.")

    X_train = train_df[feature_columns]
    y_train = train_df["target"]
    X_valid = valid_df[feature_columns]
    y_valid = valid_df["target"]

    model = LGBMRegressor(
        objective="regression",
        n_estimators=2000,
        learning_rate=0.05,
        max_depth=-1,
        subsample=0.9,
        colsample_bytree=0.9,
        random_state=42,
    )

    model.fit(
        X_train,
        y_train,
        eval_set=[(X_valid, y_valid)],
        eval_metric="rmse",
        callbacks=[
            early_stopping(stopping_rounds=50, verbose=True)
        ],
        categorical_feature=[feature_columns.index(col) for col in categorical_features],
    )

    y_pred = model.predict(X_valid)
    rmse = float(np.sqrt(np.mean((y_valid - y_pred) ** 2)))
    metrics = {"rmse": round(rmse, 4)}

    joblib.dump(model, DEFAULT_MODEL_PATH)
    version = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    _save_metadata(metrics, version=version, model_path=DEFAULT_MODEL_PATH)

    LOGGER.info("ml.training.lgbm.completed", metrics=metrics, registros=len(dataset))
    return metrics


def _load_model() -> LGBMRegressor:
    if not DEFAULT_MODEL_PATH.is_file():
        raise FileNotFoundError(
            "Modelo global não encontrado. Execute `train_global_lgbm_model()` antes de gerar previsões."
        )
    return joblib.load(DEFAULT_MODEL_PATH)


def _prepare_history_for_prediction(session: Session, produto_id: int) -> pd.Series:
    registros = list(
        session.exec(
            select(PrecosHistoricos)
            .where(PrecosHistoricos.produto_id == produto_id)
            .order_by(PrecosHistoricos.coletado_em)
        )
    )
    if len(registros) < MINIMUM_HISTORY_POINTS:
        raise InsufficientHistoryError(
            f"Produto {produto_id} possui apenas {len(registros)} registros. É necessário {MINIMUM_HISTORY_POINTS}."
        )

    series = []
    for registro in registros:
        coleta = registro.coletado_em
        if coleta.tzinfo is None:
            coleta = coleta.replace(tzinfo=timezone.utc)
        coleta = coleta.astimezone(timezone.utc).replace(tzinfo=None)
        series.append((coleta.date(), float(registro.preco)))

    df = pd.DataFrame(series, columns=["ds", "price"])
    df = df.groupby("ds").agg(price=("price", "mean"))
    df = df.asfreq("D")
    df["price"] = df["price"].interpolate(method="time").ffill().bfill()
    return df["price"]


def _build_feature_row(
    *,
    produto_id_code: int,
    date: datetime,
    history_window: deque,
    feature_columns: List[str],
) -> Dict[str, float]:
    values = list(history_window)
    latest_series = pd.Series(values)

    def _get_lag(offset: int) -> float:
        if len(values) < offset:
            return float(values[-1])
        return float(values[-offset])

    def _rolling(window: int) -> tuple[float, float]:
        subset = latest_series.tail(window)
        return float(subset.mean()), float(subset.std(ddof=0))

    mean_7, std_7 = _rolling(7)
    mean_30, std_30 = _rolling(30)

    row = {
        "produto_id": produto_id_code,
        "day_of_week": date.weekday(),
        "week_of_year": date.isocalendar().week,
        "month": date.month,
        "lag_1": _get_lag(1),
        "lag_7": _get_lag(7),
        "lag_14": _get_lag(14),
        "rolling_mean_7": mean_7,
        "rolling_std_7": std_7 if np.isfinite(std_7) else 0.0,
        "rolling_mean_30": mean_30,
        "rolling_std_30": std_30 if np.isfinite(std_30) else 0.0,
    }

    return {column: row[column] for column in feature_columns}


def predict_prices(skus: List[str], horizon_days: int) -> Dict[str, List[float]]:
    """Gera previsões diárias para uma lista de SKUs usando o modelo global."""

    if horizon_days < 1:
        raise ValueError("O horizonte de previsão deve ser maior ou igual a 1.")

    model = _load_model()
    feature_columns = [
        "produto_id",
        "day_of_week",
        "week_of_year",
        "month",
        "lag_1",
        "lag_7",
        "lag_14",
        "rolling_mean_7",
        "rolling_std_7",
        "rolling_mean_30",
        "rolling_std_30",
    ]

    with Session(engine) as session:
        produtos = list(session.exec(select(Produto).where(Produto.sku.in_(skus))))
        if not produtos:
            raise ValueError("Nenhum SKU válido encontrado para previsão.")

        id_map = {produto.sku: produto.id for produto in produtos}
        categorical_map = {produto.id: idx for idx, produto in enumerate(sorted(produtos, key=lambda p: p.id))}

        forecasts: Dict[str, List[float]] = {}

        for sku, produto_id in id_map.items():
            history_series = _prepare_history_for_prediction(session, produto_id)

            window = deque(history_series.tail(60).tolist(), maxlen=60)
            produto_code = categorical_map[produto_id]

            last_date = history_series.index[-1]
            sku_predictions: List[float] = []

            for step in range(1, horizon_days + 1):
                next_date = last_date + timedelta(days=step)
                feature_row = _build_feature_row(
                    produto_id_code=produto_code,
                    date=datetime.combine(next_date, datetime.min.time()),
                    history_window=window,
                    feature_columns=feature_columns,
                )

                feature_values = np.array([feature_row[col] for col in feature_columns]).reshape(1, -1)
                prediction = float(model.predict(feature_values)[0])

                window.append(prediction)
                sku_predictions.append(prediction)

            forecasts[sku] = sku_predictions

    return forecasts


__all__ = [
    "train_global_lgbm_model",
    "predict_prices",
    "InsufficientHistoryError",
]
