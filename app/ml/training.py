"""Prophet training pipeline leveraging Mercado Livre price history."""

from __future__ import annotations

import io
import pickle
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable

import numpy as np
import pandas as pd
import structlog
from matplotlib import pyplot as plt
from prophet import Prophet
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas
from sqlmodel import Session, select

from app.core.database import engine
from app.models.models import ModeloPredicao, PrecosHistoricos, Produto

LOGGER = structlog.get_logger(__name__)

FORECAST_HORIZON_DAYS = 30
MINIMUM_HISTORY_POINTS = 5
ROOT_DIR = Path(__file__).resolve().parents[2]
MODELS_DIR = ROOT_DIR / "models"
REPORTS_DIR = ROOT_DIR / "reports"

for directory in (MODELS_DIR, REPORTS_DIR):
    directory.mkdir(parents=True, exist_ok=True)


def train_prophet_model(produto_id: int) -> str:
    """Train a Prophet model based on Mercado Livre price history and return the PDF path."""

    LOGGER.info("ml.training.start", produto_id=produto_id)

    with Session(engine) as session:
        produto = session.get(Produto, produto_id)
        if produto is None:
            LOGGER.warning("ml.training.product_not_found", produto_id=produto_id)
            raise ValueError(f"Produto {produto_id} não encontrado para treinamento.")

        precos = list(
            session.exec(
                select(PrecosHistoricos)
                .where(PrecosHistoricos.produto_id == produto_id)
                .order_by(PrecosHistoricos.coletado_em)
            )
        )

        if len(precos) < MINIMUM_HISTORY_POINTS:
            LOGGER.warning(
                "ml.training.insufficient_history",
                produto_id=produto_id,
                registros=len(precos),
                minimo=MINIMUM_HISTORY_POINTS,
            )
            raise ValueError(
                "É necessário pelo menos 5 registros de preços históricos para treinar o modelo."
            )

        history_df = _prepare_history_dataframe(precos)

        model = Prophet(daily_seasonality=True, weekly_seasonality=True, yearly_seasonality=False)
        model.fit(history_df)

        future = model.make_future_dataframe(periods=FORECAST_HORIZON_DAYS, freq="D")
        forecast = model.predict(future)

        metrics = _calculate_metrics(history_df, forecast)
        timestamp = datetime.now(timezone.utc)
        version = timestamp.strftime("%Y%m%dT%H%M%SZ")

        model_path = MODELS_DIR / f"{produto_id}_{version}.pkl"
        with model_path.open("wb") as artifact:
            pickle.dump(model, artifact)

        pdf_path = REPORTS_DIR / f"{produto_id}_{version}.pdf"
        report_data = ReportData(
            produto_nome=produto.nome,
            history=history_df,
            forecast=forecast,
            metrics=metrics,
            treinado_em=timestamp,
            pdf_path=pdf_path,
        )
        _generate_forecast_report(report_data=report_data)

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
        "ml.training.completed",
        produto_id=produto_id,
        pdf_path=str(pdf_path),
        metricas=metrics,
    )

    return str(pdf_path)


def _prepare_history_dataframe(precos: Iterable[PrecosHistoricos]) -> pd.DataFrame:
    """Build a Prophet-compatible dataframe from price history entries."""

    data = pd.DataFrame(
        {
            "ds": [registro.coletado_em.replace(tzinfo=None) for registro in precos],
            "y": [float(registro.preco) for registro in precos],
        }
    ).sort_values("ds")

    return data


def _calculate_metrics(history: pd.DataFrame, forecast: pd.DataFrame) -> Dict[str, float]:
    """Calculate MSE and RMSE for in-sample predictions."""

    merged = history.merge(forecast[["ds", "yhat"]], on="ds", how="left")
    merged = merged.dropna(subset=["yhat"])
    y_true = merged["y"].to_numpy(dtype=float)
    y_pred = merged["yhat"].to_numpy(dtype=float)

    mse = float(np.mean((y_true - y_pred) ** 2))
    rmse = float(np.sqrt(mse))

    return {"mse": round(mse, 4), "rmse": round(rmse, 4)}


@dataclass
class ReportData:
    """Encapsulates all data needed to generate a forecast report."""

    produto_nome: str
    history: pd.DataFrame
    forecast: pd.DataFrame
    metrics: Dict[str, float]
    treinado_em: datetime
    pdf_path: Path


def _generate_forecast_report(report_data: ReportData) -> None:
    """Create a PDF report summarizing the Prophet training run."""

    chart_stream = _create_forecast_plot(
        produto_nome=report_data.produto_nome,
        history=report_data.history,
        forecast=report_data.forecast,
    )

    pdf = canvas.Canvas(str(report_data.pdf_path), pagesize=A4)
    width, height = A4
    margin = 40

    pdf.setTitle(f"Relatório de Re-Treino — {report_data.produto_nome}")

    pdf.setFont("Helvetica-Bold", 18)
    pdf.drawString(margin, height - margin, f"Relatório de Re-Treino — {report_data.produto_nome}")

    pdf.setFont("Helvetica", 12)
    info_lines = [
        f"Produto: {report_data.produto_nome}",
        f"Gerado em: {report_data.treinado_em.strftime('%d/%m/%Y %H:%M UTC')}",
        f"Horizonte de previsão: {FORECAST_HORIZON_DAYS} dias",
    ]
    y_position = height - margin - 30
    for line in info_lines:
        pdf.drawString(margin, y_position, line)
        y_position -= 18

    image_reader = ImageReader(chart_stream)
    image_height = height / 2
    pdf.drawImage(
        image_reader,
        margin,
        (height / 2) - (image_height / 2) - 20,
        width=width - (2 * margin),
        height=image_height,
        preserveAspectRatio=True,
        mask="auto",
    )

    pdf.showPage()

    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawString(margin, height - margin, "Métricas de Desempenho")

    pdf.setFont("Helvetica", 12)
    metric_lines = [
        f"MSE: {report_data.metrics.get('mse', 0.0):.4f}",
        f"RMSE: {report_data.metrics.get('rmse', 0.0):.4f}",
        "Observações:",
        "Valores menores indicam melhor aderência do modelo aos dados históricos.",
    ]
    y_position = height - margin - 30
    for line in metric_lines:
        pdf.drawString(margin, y_position, line)
        y_position -= 18

    pdf.save()


def _create_forecast_plot(
    *, produto_nome: str, history: pd.DataFrame, forecast: pd.DataFrame
) -> io.BytesIO:
    """Return an in-memory PNG plot combining history and forecast."""

    plt.style.use("seaborn-v0_8")
    fig, ax = plt.subplots(figsize=(9, 5))

    ax.plot(history["ds"], history["y"], label="Histórico", marker="o")

    cutoff_date = history["ds"].max()
    forecast_future = forecast[forecast["ds"] >= cutoff_date]
    ax.plot(
        forecast_future["ds"],
        forecast_future["yhat"],
        label="Previsão",
        color="tab:orange",
    )
    ax.fill_between(
        forecast_future["ds"],
        forecast_future["yhat_lower"],
        forecast_future["yhat_upper"],
        color="tab:orange",
        alpha=0.2,
        label="Intervalo de confiança",
    )

    ax.set_title(f"Histórico e Previsão de Preços — {produto_nome}")
    ax.set_xlabel("Data")
    ax.set_ylabel("Preço (BRL)")
    ax.grid(True, linestyle="--", alpha=0.4)
    ax.legend()

    fig.autofmt_xdate()

    buffer = io.BytesIO()
    fig.savefig(buffer, format="png", bbox_inches="tight")
    plt.close(fig)
    buffer.seek(0)
    return buffer


__all__ = ["train_prophet_model", "FORECAST_HORIZON_DAYS"]
