"""Prophet training pipelines leveraging Mercado Livre price history."""

from __future__ import annotations

import io
import pickle
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Sequence

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


class InsufficientHistoryError(RuntimeError):
    """Raised when a product does not provide enough samples for training."""


@dataclass
class TrainingOutcome:
    """Artifacts produced while training a single product."""

    produto_id: int
    produto_nome: str
    history: pd.DataFrame
    forecast: pd.DataFrame
    metrics: Dict[str, float]
    treinado_em: datetime
    version: str
    model_path: Path


@dataclass
class SkippedProduct:
    """Metadata for products skipped during a bulk training run."""

    produto_id: int
    produto_nome: str
    reason: str


@dataclass
class BulkTrainingResult:
    """Result payload describing the consolidated training execution."""

    pdf_path: str
    trained_products: List[int]
    skipped: List[SkippedProduct]


@dataclass
class PDFLayoutConfig:
    """Configuration for PDF layout and styling."""
    
    width: float
    height: float
    margin: float
    title_font_size: int = 18
    section_font_size: int = 16
    body_font_size: int = 12


def train_prophet_model(produto_id: int) -> str:
    """Train a Prophet model for a single product and return the PDF path."""

    LOGGER.info("ml.training.start", produto_id=produto_id)
    run_timestamp = datetime.now(timezone.utc)

    with Session(engine) as session:
        produto = session.get(Produto, produto_id)
        if produto is None:
            LOGGER.warning("ml.training.product_not_found", produto_id=produto_id)
            raise ValueError(f"Produto {produto_id} não encontrado para treinamento.")

        try:
            outcome = _train_product(session=session, produto=produto, run_timestamp=run_timestamp)
        except InsufficientHistoryError as exc:
            raise ValueError(
                "É necessário pelo menos 5 registros de preços históricos para treinar o modelo."
            ) from exc

    pdf_path = REPORTS_DIR / f"{produto_id}_{outcome.version}.pdf"
    _generate_single_product_report(outcome=outcome, pdf_path=pdf_path)

    LOGGER.info(
        "ml.training.completed",
        produto_id=produto_id,
        pdf_path=str(pdf_path),
        metricas=outcome.metrics,
    )

    return str(pdf_path)


def train_all_products() -> BulkTrainingResult:
    """Train Prophet models for every product and consolidate the report into a single PDF."""

    LOGGER.info("ml.training.bulk.start")
    run_timestamp = datetime.now(timezone.utc)

    with Session(engine) as session:
        produtos = list(session.exec(select(Produto).order_by(Produto.nome)))

        if not produtos:
            raise ValueError("Nenhum produto cadastrado para treinamento.")

        outcomes, skipped = _process_products_for_training(session, produtos, run_timestamp)

    if not outcomes:
        raise ValueError("Nenhum produto possui histórico suficiente para treinamento.")

    consolidated_pdf = REPORTS_DIR / f"catalogo_completo_{run_timestamp.strftime('%Y%m%dT%H%M%SZ')}.pdf"
    _generate_bulk_report(
        outcomes=outcomes,
        skipped=skipped,
        pdf_path=consolidated_pdf,
        generated_at=run_timestamp,
    )

    trained_ids = [outcome.produto_id for outcome in outcomes]
    LOGGER.info(
        "ml.training.bulk.completed",
        treinados=trained_ids,
        ignorados=[item.produto_id for item in skipped],
        pdf_path=str(consolidated_pdf),
    )

    return BulkTrainingResult(
        pdf_path=str(consolidated_pdf),
        trained_products=trained_ids,
        skipped=skipped,
    )


def _process_products_for_training(
    session: Session, produtos: List[Produto], run_timestamp: datetime
) -> tuple[List[TrainingOutcome], List[SkippedProduct]]:
    """Process all products for training and return outcomes and skipped products."""
    
    outcomes: List[TrainingOutcome] = []
    skipped: List[SkippedProduct] = []

    for produto in produtos:
        try:
            outcome = _train_product(session=session, produto=produto, run_timestamp=run_timestamp)
            outcomes.append(outcome)
        except InsufficientHistoryError as exc:
            session.rollback()
            skipped.append(
                SkippedProduct(
                    produto_id=produto.id,
                    produto_nome=_resolve_produto_nome(produto),
                    reason=str(exc),
                )
            )
            LOGGER.warning(
                "ml.training.bulk.skip.insufficient_history",
                produto_id=produto.id,
                registros=_count_price_records(session=session, produto_id=produto.id),
                minimo=MINIMUM_HISTORY_POINTS,
            )
        except Exception as exc:  # noqa: BLE001 - surface unexpected issues
            session.rollback()
            skipped.append(
                SkippedProduct(
                    produto_id=produto.id,
                    produto_nome=_resolve_produto_nome(produto),
                    reason=str(exc),
                )
            )
            LOGGER.error(
                "ml.training.bulk.skip.error",
                produto_id=produto.id,
                error=str(exc),
            )
    
    return outcomes, skipped


def _train_product(*, session: Session, produto: Produto, run_timestamp: datetime) -> TrainingOutcome:
    """Execute Prophet training for the provided product within the current session."""

    precos = list(
        session.exec(
            select(PrecosHistoricos)
            .where(PrecosHistoricos.produto_id == produto.id)
            .order_by(PrecosHistoricos.coletado_em)
        )
    )

    if len(precos) < MINIMUM_HISTORY_POINTS:
        raise InsufficientHistoryError(
            f"Histórico insuficiente ({len(precos)}/{MINIMUM_HISTORY_POINTS})"
        )

    history_df = _prepare_history_dataframe(precos)

    model = Prophet(daily_seasonality=True, weekly_seasonality=True, yearly_seasonality=False)
    model.fit(history_df)

    future = model.make_future_dataframe(periods=FORECAST_HORIZON_DAYS, freq="D")
    forecast = model.predict(future)

    metrics = _calculate_metrics(history_df, forecast)
    version = run_timestamp.strftime("%Y%m%dT%H%M%SZ")
    model_path = MODELS_DIR / f"{produto.id}_{version}.pkl"

    with model_path.open("wb") as artifact:
        pickle.dump(model, artifact)

    metadata = ModeloPredicao(
        produto_id=produto.id,
        modelo_tipo="prophet",
        versao=version,
        caminho_modelo=str(model_path),
        metricas=metrics,
        treinado_em=run_timestamp,
    )
    session.add(metadata)
    session.commit()

    return TrainingOutcome(
        produto_id=produto.id,
        produto_nome=_resolve_produto_nome(produto),
        history=history_df,
        forecast=forecast,
        metrics=metrics,
        treinado_em=run_timestamp,
        version=version,
        model_path=model_path,
    )


def _count_price_records(*, session: Session, produto_id: int) -> int:
    """Return the number of price records for logging purposes."""

    return len(
        session.exec(
            select(PrecosHistoricos).where(PrecosHistoricos.produto_id == produto_id)
        ).all()
    )


def _resolve_produto_nome(produto: Produto) -> str:
    """Return a human readable product name for reporting."""

    if produto.nome:
        return produto.nome
    if produto.sku:
        return produto.sku
    return f"ID {produto.id}"


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


def _create_pdf_canvas(pdf_path: Path, title: str) -> tuple[canvas.Canvas, PDFLayoutConfig]:
    """Create a PDF canvas with standard configuration."""
    
    pdf = canvas.Canvas(str(pdf_path), pagesize=A4)
    width, height = A4
    margin = 40
    
    config = PDFLayoutConfig(width=width, height=height, margin=margin)
    pdf.setTitle(title)
    
    return pdf, config


def _add_pdf_header(pdf: canvas.Canvas, config: PDFLayoutConfig, title: str) -> float:
    """Add header to PDF and return the y position for content."""
    
    pdf.setFont("Helvetica-Bold", config.title_font_size)
    pdf.drawString(config.margin, config.height - config.margin, title)
    
    return config.height - config.margin - 30


def _add_info_lines(pdf: canvas.Canvas, config: PDFLayoutConfig, lines: List[str], y_start: float) -> float:
    """Add information lines to PDF and return final y position."""
    
    pdf.setFont("Helvetica", config.body_font_size)
    y_position = y_start
    
    for line in lines:
        pdf.drawString(config.margin, y_position, line)
        y_position -= 18
    
    return y_position


def _add_chart_to_pdf(pdf: canvas.Canvas, config: PDFLayoutConfig, chart_stream: io.BytesIO, y_offset: float = 20) -> None:
    """Add chart image to PDF."""
    
    image_reader = ImageReader(chart_stream)
    image_height = config.height / 2
    pdf.drawImage(
        image_reader,
        config.margin,
        (config.height / 2) - (image_height / 2) - y_offset,
        width=config.width - (2 * config.margin),
        height=image_height,
        preserveAspectRatio=True,
        mask="auto",
    )


def _generate_single_product_report(*, outcome: TrainingOutcome, pdf_path: Path) -> None:
    """Create a PDF report summarizing the Prophet training run for one product."""

    chart_stream = _create_forecast_plot(
        produto_nome=outcome.produto_nome,
        history=outcome.history,
        forecast=outcome.forecast,
    )

    pdf, config = _create_pdf_canvas(pdf_path, f"Relatório de Re-Treino — {outcome.produto_nome}")
    
    # First page - header and chart
    y_position = _add_pdf_header(pdf, config, f"Relatório de Re-Treino — {outcome.produto_nome}")
    
    info_lines = [
        f"Produto: {outcome.produto_nome}",
        f"Gerado em: {outcome.treinado_em.strftime('%d/%m/%Y %H:%M UTC')}",
        f"Horizonte de previsão: {FORECAST_HORIZON_DAYS} dias",
    ]
    _add_info_lines(pdf, config, info_lines, y_position)
    _add_chart_to_pdf(pdf, config, chart_stream)

    # Second page - metrics
    pdf.showPage()
    y_position = _add_pdf_header(pdf, config, "Métricas de Desempenho")
    
    metric_lines = [
        f"MSE: {outcome.metrics.get('mse', 0.0):.4f}",
        f"RMSE: {outcome.metrics.get('rmse', 0.0):.4f}",
        "Observações:",
        "Valores menores indicam melhor aderência do modelo aos dados históricos.",
    ]
    _add_info_lines(pdf, config, metric_lines, y_position)

    pdf.save()


def _generate_bulk_report_summary(
    pdf: canvas.Canvas, config: PDFLayoutConfig, summary_stats: Dict[str, int], generated_at: datetime
) -> float:
    """Generate the summary section of bulk report and return y position."""
    
    y_position = _add_pdf_header(pdf, config, "Relatório de Re-Treino — Catálogo Completo")
    
    summary_lines = [
        f"Gerado em: {generated_at.strftime('%d/%m/%Y %H:%M UTC')}",
        f"Produtos treinados: {summary_stats['trained_count']}",
        f"Produtos com dados insuficientes: {summary_stats['skipped_count']}",
    ]
    return _add_info_lines(pdf, config, summary_lines, y_position)


def _add_trained_products_section(
    pdf: canvas.Canvas, config: PDFLayoutConfig, outcomes: Sequence[TrainingOutcome], y_position: float
) -> float:
    """Add trained products section to PDF and return final y position."""
    
    pdf.setFont("Helvetica-Bold", 14)
    pdf.drawString(config.margin, y_position - 6, "Resumo dos produtos treinados")
    y_position -= 28
    pdf.setFont("Helvetica", config.body_font_size)

    for outcome in outcomes:
        if y_position < config.margin + 40:
            pdf.showPage()
            y_position = config.height - config.margin
            pdf.setFont("Helvetica", config.body_font_size)
        
        rmse = outcome.metrics.get("rmse")
        rmse_text = f"{rmse:.4f}" if rmse is not None else "N/D"
        pdf.drawString(
            config.margin,
            y_position,
            f"- {outcome.produto_nome} (RMSE: {rmse_text})",
        )
        y_position -= 16
    
    return y_position


def _add_skipped_products_section(
    pdf: canvas.Canvas, config: PDFLayoutConfig, skipped: Sequence[SkippedProduct], y_position: float
) -> None:
    """Add skipped products section to PDF."""
    
    if not skipped:
        return
    
    if y_position < config.margin + 60:
        pdf.showPage()
        y_position = config.height - config.margin
    
    pdf.setFont("Helvetica-Bold", 14)
    pdf.drawString(config.margin, y_position - 6, "Produtos ignorados")
    y_position -= 28
    pdf.setFont("Helvetica", config.body_font_size)
    
    for item in skipped:
        if y_position < config.margin + 40:
            pdf.showPage()
            y_position = config.height - config.margin
            pdf.setFont("Helvetica", config.body_font_size)
        pdf.drawString(config.margin, y_position, f"- {item.produto_nome}: {item.reason}")
        y_position -= 16


def _generate_bulk_report(
    *,
    outcomes: Sequence[TrainingOutcome],
    skipped: Sequence[SkippedProduct],
    pdf_path: Path,
    generated_at: datetime,
) -> None:
    """Render a consolidated PDF report spanning every trained product."""

    pdf, config = _create_pdf_canvas(pdf_path, "Relatório de Re-Treino — Catálogo Completo")

    # Summary page
    summary_stats = {"trained_count": len(outcomes), "skipped_count": len(skipped)}
    y_position = _generate_bulk_report_summary(pdf, config, summary_stats, generated_at)
    y_position = _add_trained_products_section(pdf, config, outcomes, y_position)
    _add_skipped_products_section(pdf, config, skipped, y_position)

    pdf.showPage()

    # Individual product pages
    for outcome in outcomes:
        _draw_product_page(pdf, config, outcome)

    pdf.save()


def _draw_product_page(pdf: canvas.Canvas, config: PDFLayoutConfig, outcome: TrainingOutcome) -> None:
    """Render a single product page inside a consolidated report."""

    y_position = _add_pdf_header(pdf, config, outcome.produto_nome)
    
    info_lines = [
        f"Treinado em: {outcome.treinado_em.strftime('%d/%m/%Y %H:%M UTC')}",
        f"MSE: {outcome.metrics.get('mse', float('nan')):.4f}",
        f"RMSE: {outcome.metrics.get('rmse', float('nan')):.4f}",
    ]
    _add_info_lines(pdf, config, info_lines, y_position)

    chart_stream = _create_forecast_plot(
        produto_nome=outcome.produto_nome,
        history=outcome.history,
        forecast=outcome.forecast,
    )
    _add_chart_to_pdf(pdf, config, chart_stream, y_offset=30)

    pdf.showPage()


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


__all__ = [
    "train_prophet_model",
    "train_all_products",
    "FORECAST_HORIZON_DAYS",
    "BulkTrainingResult",
    "SkippedProduct",
]
