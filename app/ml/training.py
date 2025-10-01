"""Prophet-based training utilities for demand forecasting."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict

import numpy as np
import pandas as pd
from matplotlib import pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from prophet import Prophet
from prophet.serialize import model_to_json
from sqlmodel import Session, select

from app.core.database import engine
from app.models.models import ModeloPredicao, Produto, VendasHistoricas

LOGGER = logging.getLogger(__name__)

FORECAST_HORIZON_DAYS = 30
ROOT_DIR = Path(__file__).resolve().parents[2]
ARTIFACTS_DIR = ROOT_DIR / "artifacts"
MODELS_DIR = ARTIFACTS_DIR / "models"
REPORTS_DIR = ARTIFACTS_DIR / "reports"

for directory in (ARTIFACTS_DIR, MODELS_DIR, REPORTS_DIR):
    directory.mkdir(parents=True, exist_ok=True)


def train_prophet_model(produto_id: int) -> str:
    """Train a Prophet model for the given product and return the generated PDF report path."""

    LOGGER.info("Iniciando treinamento Prophet", extra={"produto_id": produto_id})

    with Session(engine) as session:
        produto = session.get(Produto, produto_id)
        if produto is None:
            raise ValueError(f"Produto {produto_id} não encontrado para treinamento.")

        vendas = session.exec(
            select(VendasHistoricas)
            .where(VendasHistoricas.produto_id == produto_id)
            .order_by(VendasHistoricas.data_venda)
        ).all()

        if len(vendas) < 5:
            raise ValueError("É necessário pelo menos 5 registros históricos para treinar o modelo.")

        history = pd.DataFrame(
            {
                "ds": [sale.data_venda for sale in vendas],
                "y": [float(sale.quantidade) for sale in vendas],
            }
        ).sort_values("ds")

        model = Prophet(daily_seasonality=True, weekly_seasonality=True, yearly_seasonality=False)
        model.fit(history)

        future = model.make_future_dataframe(periods=FORECAST_HORIZON_DAYS, freq="D")
        forecast = model.predict(future)

        metrics = _calculate_metrics(history, forecast)
        timestamp = datetime.now(timezone.utc)
        version = timestamp.strftime("%Y%m%dT%H%M%SZ")

        model_path = MODELS_DIR / f"produto_{produto_id}_{version}.json"
        model_path.write_text(json.dumps(model_to_json(model)), encoding="utf-8")

        pdf_path = REPORTS_DIR / f"produto_{produto_id}_{version}.pdf"
        _generate_forecast_report(
            produto_nome=produto.nome,
            forecast_data={
                "history": history,
                "forecast": forecast,
                "metrics": metrics,
                "pdf_path": pdf_path,
            }
        )

        metadata = ModeloPredicao(
            produto_id=produto_id,
            modelo_tipo="prophet",
            versao=version,
            caminho_modelo=str(model_path),
            metricas=metrics,
            treinado_em=timestamp,
        )
        session.add(metadata)
        session.commit()

    LOGGER.info(
        "Treinamento concluído",
        extra={"produto_id": produto_id, "pdf_path": str(pdf_path), "metricas": metrics},
    )

    return str(pdf_path)


def _calculate_metrics(history: pd.DataFrame, forecast: pd.DataFrame) -> Dict[str, float]:
    """Compute RMSE and MAPE metrics for the in-sample forecast."""

    y_true = history["y"].to_numpy(dtype=float)
    y_pred = forecast.loc[: len(history) - 1, "yhat"].to_numpy(dtype=float)

    rmse = float(np.sqrt(np.mean((y_true - y_pred) ** 2)))
    denominator = np.clip(np.abs(y_true), a_min=1e-6, a_max=None)
    mape = float(np.mean(np.abs((y_true - y_pred) / denominator)) * 100.0)

    return {"rmse": round(rmse, 4), "mape": round(mape, 2)}
def _generate_forecast_report(
    produto_nome: str,
    forecast_data: Dict,
) -> None:
    """Generate a PDF report with the historical data and Prophet forecast."""

    history = forecast_data["history"]
    forecast = forecast_data["forecast"] 
    metrics = forecast_data["metrics"]
    pdf_path = forecast_data["pdf_path"]



    with PdfPages(pdf_path) as pdf:
        plt.style.use("seaborn-v0_8")

        fig, ax = plt.subplots(figsize=(11.69, 8.27))  # A4 landscape in inches
        ax.plot(history["ds"], history["y"], label="Histórico", marker="o")
        ax.plot(forecast["ds"], forecast["yhat"], label="Previsão", color="tab:orange")
        ax.fill_between(
            forecast["ds"],
            forecast["yhat_lower"],
            forecast["yhat_upper"],
            color="tab:orange",
            alpha=0.2,
            label="Intervalo de confiança",
        )
        ax.set_title(f"Demanda - {produto_nome}")
        ax.set_xlabel("Data")
        ax.set_ylabel("Quantidade diária")
        ax.legend()
        ax.grid(True, linestyle="--", alpha=0.5)
        pdf.savefig(fig, bbox_inches="tight")
        plt.close(fig)

        fig, ax = plt.subplots(figsize=(8.27, 11.69))  # A4 portrait for metrics
        ax.axis("off")
        lines = [
            f"Produto: {produto_nome}",
            f"RMSE: {metrics['rmse']:.2f}",
            f"MAPE: {metrics['mape']:.2f}%",
            f"Período previsto: {FORECAST_HORIZON_DAYS} dias",
            f"Relatório gerado em: {datetime.now(timezone.utc).strftime('%d/%m/%Y %H:%M UTC')}",
        ]
        ax.text(0.05, 0.95, "\n".join(lines), fontsize=12, va="top")
        pdf.savefig(fig, bbox_inches="tight")
        plt.close(fig)
