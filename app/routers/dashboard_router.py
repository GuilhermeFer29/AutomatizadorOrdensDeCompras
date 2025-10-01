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
def render_dashboard(
  produto_id: Optional[int] = Query(default=None),
  busca: Optional[str] = Query(default=None, alias="q"),
) -> HTMLResponse:
  """Render the dashboard with historical prices, forecast curve and metrics."""

  termo_busca = (busca or "").strip()
  aviso_busca: Optional[str] = None

  with Session(engine) as session:
    produtos_catalogo = list(session.exec(select(Produto).order_by(Produto.nome)))
    if not produtos_catalogo:
      LOGGER.warning("dashboard.no_products")
      return HTMLResponse("<h1>Nenhum produto cadastrado.</h1>", status_code=200)

    produtos_exibidos = produtos_catalogo
    if termo_busca:
      produtos_filtrados = _filter_products(produtos_catalogo, termo_busca)
      if produtos_filtrados:
        produtos_exibidos = produtos_filtrados
      else:
        aviso_busca = f"Nenhum produto encontrado para '{termo_busca}'."
        termo_busca = ""

    produto = _select_produto(produtos_exibidos, produto_id)
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
      produtos=produtos_exibidos,
      produto_selecionado=produto,
      chart_payload={"labels": [], "history": [], "forecast": []},
      metricas={},
      treinado_em=None,
      aviso="Nenhum preço coletado para este produto ainda.",
      busca=termo_busca,
      aviso_busca=aviso_busca,
    )
    return HTMLResponse(_render_template(template))

  history_frame = _build_history_frame(precos)
  chart_payload, treinado_em, metricas = _load_forecast_payload(
    history_frame=history_frame,
    metadata=metadata,
  )

  template = TemplateData(
    produtos=produtos_exibidos,
    produto_selecionado=produto,
    chart_payload=chart_payload,
    metricas=metricas,
    treinado_em=treinado_em,
    aviso=None,
    busca=termo_busca,
    aviso_busca=aviso_busca,
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


def _filter_products(produtos: List[Produto], termo: str) -> List[Produto]:
  """Filter products by name or SKU using the provided search term."""

  termo_lower = termo.lower()
  return [
    produto
    for produto in produtos
    if termo_lower in (produto.nome or "").lower()
    or termo_lower in (produto.sku or "").lower()
  ]


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
  body { font-family: 'Inter', 'Segoe UI', sans-serif; margin: 24px; color: #0f172a; background-color: #f8fafc; }
  header { display: flex; flex-wrap: wrap; gap: 16px; align-items: flex-end; margin-bottom: 24px; }
  header h1 { margin: 0; font-size: 1.75rem; }
  .metrics { font-size: 0.9rem; color: #475569; margin-top: 4px; }
  .selectors { display: flex; gap: 12px; align-items: flex-end; flex-wrap: wrap; }
  .selectors label { display: block; font-size: 0.75rem; text-transform: uppercase; color: #64748b; letter-spacing: 0.05em; margin-bottom: 4px; }
  .selectors input[type="search"], .selectors select { padding: 8px 12px; border-radius: 8px; border: 1px solid #cbd5f5; background: #ffffff; font-size: 0.95rem; min-width: 220px; box-shadow: 0 1px 2px rgba(15, 23, 42, 0.08); }
  .selectors button { padding: 9px 18px; border-radius: 8px; background: #2563eb; color: #ffffff; border: none; cursor: pointer; font-size: 0.95rem; transition: background 0.2s ease; box-shadow: 0 8px 16px rgba(37, 99, 235, 0.25); }
  .selectors button:hover { background: #1d4ed8; }
  section { background: #ffffff; border-radius: 16px; padding: 24px; box-shadow: 0 16px 28px rgba(15, 23, 42, 0.08); }
  canvas { max-width: 100%; }
  .warning { color: #b91c1c; margin-top: 16px; font-weight: 600; }
  .search-notice { color: #6d28d9; margin-bottom: 16px; font-weight: 500; }
  footer { margin-top: 32px; font-size: 0.75rem; color: #64748b; text-align: center; }
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
    <div>
      <label for="search">Buscar</label>
      <input type="search" id="search" name="q" placeholder="Nome ou SKU" value="{template_data['search_value']}" />
    </div>
    <div>
      <label for="produto">Produto</label>
      <select id="produto" name="produto_id" onchange="this.form.submit()">
      {template_data['options_html']}
      </select>
    </div>
    <button type="submit">Aplicar</button>
  </form>
  </header>
  """


def _build_main_section(template_data: Dict[str, str]) -> str:
  """Build the main content section."""
  return f"""
  <section>
  {template_data['search_notice_html']}
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
    busca: str
    aviso_busca: Optional[str]


def _prepare_template_data(template_data: TemplateData) -> Dict[str, str]:
    """Prepare all template data for rendering."""

    return {
        "produto_nome": template_data.produto_selecionado.nome,
        "options_html": _build_product_options(template_data.produtos, template_data.produto_selecionado),
        "chart_json": json.dumps(template_data.chart_payload, ensure_ascii=False),
        "metricas_html": _format_metrics(template_data.metricas),
        "treino_texto": _format_training_date(template_data.treinado_em),
        "aviso_html": f"<p class='warning'>{template_data.aviso}</p>" if template_data.aviso else "",
        "search_value": template_data.busca,
        "search_notice_html": (
            f"<p class='search-notice'>{template_data.aviso_busca}</p>" if template_data.aviso_busca else ""
        ),
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
