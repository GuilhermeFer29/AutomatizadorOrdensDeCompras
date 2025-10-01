"""Simple dashboard rendered via FastAPI to visualise price history and forecasts."""

from __future__ import annotations

import json
import pickle
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd
import structlog
from fastapi import APIRouter, Query
from fastapi.responses import HTMLResponse
from sqlmodel import Session, select

from app.core.database import engine
from app.ml.training import FORECAST_HORIZON_DAYS
from app.models.models import ModeloPredicao, PrecosHistoricos, Produto
from dataclasses import dataclass

LOGGER = structlog.get_logger(__name__)
router = APIRouter(tags=["dashboard"])

ROOT_DIR = Path(__file__).resolve().parents[2]


@router.get("/dashboard", response_class=HTMLResponse)
def render_dashboard(produto_id: Optional[int] = Query(default=None)) -> HTMLResponse:
    """Render the dashboard with historical prices, forecast curve and metrics."""

    with Session(engine) as session:
        produtos = list(session.exec(select(Produto).order_by(Produto.nome)))
        if not produtos:
            LOGGER.warning("dashboard.no_products")
            return HTMLResponse("<h1>Nenhum produto cadastrado.</h1>", status_code=200)

        produto = _select_produto(produtos, produto_id)
        precos = list(
            session.exec(
                select(PrecosHistoricos)
                .where(PrecosHistoricos.produto_id == produto.id)
                .order_by(PrecosHistoricos.coletado_em)
            )
        )
        metadata = session.exec(
            select(ModeloPredicao)
            .where(ModeloPredicao.produto_id == produto.id)
            .order_by(ModeloPredicao.treinado_em.desc())
        ).first()

    if not precos:
        LOGGER.info("dashboard.no_history", produto_id=produto.id)
        template = TemplateData(
            produtos=produtos,
            produto_selecionado=produto,
            chart_payload={"labels": [], "history": [], "forecast": []},
            metricas={},
            treinado_em=None,
            aviso="Nenhum preço coletado para este produto ainda.",
        )
        return HTMLResponse(_render_template(template))

    history_frame = _build_history_frame(precos)
    chart_payload, treinado_em, metricas = _load_forecast_payload(
        history_frame=history_frame,
        metadata=metadata,
    )

    template = TemplateData(
        produtos=produtos,
        produto_selecionado=produto,
        chart_payload=chart_payload,
        metricas=metricas,
        treinado_em=treinado_em,
        aviso=None,
    )
    html = _render_template(template)
    LOGGER.info("dashboard.render", produto_id=produto.id)
    return HTMLResponse(html)


def _select_produto(produtos: List[Produto], produto_id: Optional[int]) -> Produto:
    """Return the requested product if available, otherwise default to the first entry."""

    if produto_id is None:
        return produtos[0]

    for produto in produtos:
        if produto.id == produto_id:
            return produto

    return produtos[0]


def _build_history_frame(precos: List[PrecosHistoricos]) -> pd.DataFrame:
  """Convert SQLModel records into a tidy pandas dataframe."""
  frame = pd.DataFrame(
    {
      "ds": [registro.coletado_em.replace(tzinfo=None) for registro in precos],
      "y": [float(registro.preco) for registro in precos],
    }
  ).sort_values("ds")
  return frame


def _load_forecast_payload(
  *,
  history_frame: pd.DataFrame,
  metadata: Optional[ModeloPredicao],
) -> Tuple[Dict[str, List[Optional[float]]], Optional[datetime], Dict[str, float]]:
  """Load the persisted Prophet model to generate the chart payload."""
  labels, history_series = _extract_history_data(history_frame)
  
  if not metadata or not metadata.caminho_modelo:
    return _create_empty_forecast_payload(labels, history_series)
  
  metricas = {chave: float(valor) for chave, valor in (metadata.metricas or {}).items()}
  treinado_em = metadata.treinado_em
  
  forecast_data = _generate_forecast(metadata.caminho_modelo, labels)
  if forecast_data is None:
    return _create_empty_forecast_payload(labels, history_series)
  
  chart_payload = _merge_history_and_forecast(labels, history_series, forecast_data)
  return chart_payload, treinado_em, metricas


def _extract_history_data(history_frame: pd.DataFrame) -> Tuple[List[str], List[float]]:
  """Extract labels and history series from dataframe."""
  labels = [date.strftime("%Y-%m-%d") for date in history_frame["ds"].tolist()]
  history_series = [round(float(valor), 4) for valor in history_frame["y"].tolist()]
  return labels, history_series


def _create_empty_forecast_payload(
  labels: List[str], 
  history_series: List[float]
) -> Tuple[Dict[str, List[Optional[float]]], Optional[datetime], Dict[str, float]]:
  """Create payload with no forecast data."""
  forecast_series: List[Optional[float]] = [None] * len(labels)
  chart_payload = {
    "labels": labels,
    "history": history_series,
    "forecast": forecast_series,
  }
  return chart_payload, None, {}


def _generate_forecast(model_path_str: str, labels: List[str]) -> Optional[Dict[str, float]]:
  """Generate forecast using the persisted model."""
  model_path = _resolve_model_path(model_path_str)
  
  if not model_path.is_file():
    LOGGER.warning("dashboard.model_missing", caminho=str(model_path))
    return None
  
  try:
    model = _load_model(model_path)
    forecast_df = _predict_future(model, labels)
    return _extract_forecast_data(forecast_df, labels)
  except Exception as e:
    LOGGER.error("dashboard.forecast_error", error=str(e))
    return None


def _resolve_model_path(model_path_str: str) -> Path:
  """Resolve the model path, handling relative paths."""
  model_path = Path(model_path_str)
  if not model_path.is_absolute():
    model_path = ROOT_DIR / model_path
  return model_path


def _load_model(model_path: Path):
  """Load the pickled Prophet model."""
  with model_path.open("rb") as model_file:
    return pickle.load(model_file)


def _predict_future(model, labels: List[str]) -> pd.DataFrame:
  """Generate predictions using the Prophet model."""
  future = model.make_future_dataframe(periods=FORECAST_HORIZON_DAYS, freq="D")
  forecast = model.predict(future)
  forecast["date"] = forecast["ds"].dt.strftime("%Y-%m-%d")
  return forecast


def _extract_forecast_data(forecast_df: pd.DataFrame, labels: List[str]) -> Dict[str, float]:
  """Extract forecast data from the prediction dataframe."""
  latest_history_date = labels[-1]
  forecast_future = forecast_df[forecast_df["date"] >= latest_history_date]
  
  return {
    row["date"]: round(float(row["yhat"]), 4)
    for _, row in forecast_future.iterrows()
  }


def _merge_history_and_forecast(
  labels: List[str], 
  history_series: List[float], 
  forecast_data: Dict[str, float]
) -> Dict[str, List[Optional[float]]]:
  """Merge historical data with forecast predictions."""
  all_labels = sorted(set(labels + list(forecast_data.keys())))
  
  history_map = {label: None for label in all_labels}
  for label, valor in zip(labels, history_series):
    history_map[label] = valor
  
  merged_history = [history_map[label] for label in all_labels]
  merged_forecast = [forecast_data.get(label) for label in all_labels]
  
  return {
    "labels": all_labels,
    "history": merged_history,
    "forecast": merged_forecast,
  }


def _render_template(template_data: TemplateData) -> str:
  """Return the HTML for the dashboard view."""
  prepared_data = _prepare_template_data(template_data)
  return _build_html_template(prepared_data)


def _build_html_template(template_data: Dict[str, str]) -> str:
  """Build the complete HTML template."""
  return f"""
<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8" />
  <title>Dashboard de Preços e Previsão</title>
  <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.3/dist/chart.umd.min.js"></script>
  <style>
  {_get_css_styles()}
  </style>
</head>
<body>
  {_build_header_section(template_data)}
  {_build_main_section(template_data)}
  {_build_footer_section()}
  {_build_chart_script(template_data)}
</body>
</html>
"""


def _get_css_styles() -> str:
  """Return CSS styles for the dashboard."""
  return """
  body { font-family: 'Segoe UI', Arial, sans-serif; margin: 40px; color: #1f2933; }
  header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 24px; }
  .selectors select { padding: 8px 12px; font-size: 14px; }
  .metrics { font-size: 14px; color: #4b5563; }
  .warning { color: #b91c1c; margin-top: 16px; font-weight: 600; }
  canvas { max-width: 100%; }
  footer { margin-top: 32px; font-size: 12px; color: #6b7280; }
  """


def _build_header_section(template_data: Dict[str, str]) -> str:
  """Build the header section of the HTML."""
  return f"""
  <header>
  <div>
    <h1>Dashboard de Preços — {template_data['produto_nome']}</h1>
    <div class="metrics">{template_data['metricas_html']}</div>
    <div class="metrics">Último treino: {template_data['treino_texto']}</div>
  </div>
  <form class="selectors" method="get" action="/dashboard">
    <label for="produto">Produto:</label>
    <select id="produto" name="produto_id" onchange="this.form.submit()">
    {template_data['options_html']}
    </select>
  </form>
  </header>
  """


def _build_main_section(template_data: Dict[str, str]) -> str:
  """Build the main content section."""
  return f"""
  <section>
  <canvas id="priceChart" height="120"></canvas>
  {template_data['aviso_html']}
  </section>
  """


def _build_footer_section() -> str:
  """Build the footer section."""
  return f"""
  <footer>
  Horizonte de previsão: {FORECAST_HORIZON_DAYS} dias. Fonte de dados: Mercado Livre (ScraperAPI).
  </footer>
  """


def _build_chart_script(template_data: Dict[str, str]) -> str:
  """Build the Chart.js configuration script."""
  return f"""
  <script>
  const chartData = {template_data['chart_json']};
  const ctx = document.getElementById('priceChart');
  const chart = new Chart(ctx, {{
    type: 'line',
    data: {{
    labels: chartData.labels,
    datasets: [
      {{
      label: 'Histórico de preços',
      data: chartData.history,
      borderColor: '#2563eb',
      backgroundColor: 'rgba(37,99,235,0.15)',
      tension: 0.2,
      spanGaps: true,
      borderWidth: 2,
      }},
      {{
      label: 'Previsão Prophet',
      data: chartData.forecast,
      borderColor: '#f59e0b',
      backgroundColor: 'rgba(245,158,11,0.15)',
      borderDash: [6,3],
      tension: 0.2,
      spanGaps: true,
      borderWidth: 2,
      }}
    ]
    }},
    options: {{
    interaction: {{ mode: 'index', intersect: false }},
    scales: {{
      x: {{
      ticks: {{ maxRotation: 45, minRotation: 45 }},
      }},
      y: {{
      beginAtZero: false,
      ticks: {{ callback: value => 'R$ ' + Number(value).toFixed(2) }},
      }},
    }},
    plugins: {{
      legend: {{ position: 'bottom' }},
    }}
    }}
  }});
  </script>
  """


@dataclass
class TemplateData:
  """Data class to encapsulate template rendering parameters."""
  produtos: List[Produto]
  produto_selecionado: Produto
  chart_payload: Dict[str, List[Optional[float]]]
  metricas: Dict[str, float]
  treinado_em: Optional[datetime]
  aviso: Optional[str]


def _prepare_template_data(template_data: TemplateData) -> Dict[str, str]:
  """Prepare all template data for rendering."""
  return {
    "produto_nome": template_data.produto_selecionado.nome,
    "options_html": _build_product_options(template_data.produtos, template_data.produto_selecionado),
    "chart_json": json.dumps(template_data.chart_payload, ensure_ascii=False),
    "metricas_html": _format_metrics(template_data.metricas),
    "treino_texto": _format_training_date(template_data.treinado_em),
    "aviso_html": f"<p class='warning'>{template_data.aviso}</p>" if template_data.aviso else "",
  }


def _build_product_options(produtos: List[Produto], produto_selecionado: Produto) -> str:
  """Build HTML options for product selection."""
  return "\n".join([
    f'<option value="{produto.id}"'
    f" {'selected' if produto.id == produto_selecionado.id else ''}>"
    f"{produto.nome}</option>"
    for produto in produtos
  ])


def _format_metrics(metricas: Dict[str, float]) -> str:
  """Format metrics for display."""
  return " | ".join([
    f"MSE: {metricas.get('mse', float('nan')):.4f}" if "mse" in metricas else "MSE: N/D",
    f"RMSE: {metricas.get('rmse', float('nan')):.4f}" if "rmse" in metricas else "RMSE: N/D",
  ])


def _format_training_date(treinado_em: Optional[datetime]) -> str:
  """Format training date for display."""
  return (
    treinado_em.strftime("%d/%m/%Y %H:%M UTC") 
    if treinado_em 
    else "Treinamento ainda não executado"
  )
