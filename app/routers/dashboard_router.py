"""Dashboard com histórico e previsões usando o modelo global LightGBM."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import json
import pandas as pd
import structlog
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import HTMLResponse
from sqlmodel import Session, select

from app.core.database import engine
from app.ml.training import predict_prices
from app.models.models import PrecosHistoricos, Produto

LOGGER = structlog.get_logger(__name__)
router = APIRouter(tags=["dashboard"])

ROOT_DIR = Path(__file__).resolve().parents[2]
DEFAULT_HORIZON_DAYS = 14


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

    global_context = _load_global_forecast()

  history_frame = _build_history_frame(precos)

  if history_frame.empty:
    LOGGER.info("dashboard.no_history", produto_id=produto.id)
    chart_payload = _empty_chart_payload()
    metricas: Dict[str, float] = {}
    treinado_em = None
  else:
    chart_payload, metricas, treinado_em = _build_product_chart_payload(
      produto=produto,
      history_frame=history_frame,
      horizon=DEFAULT_HORIZON_DAYS,
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
    global_context=global_context,
  )
  html = _render_template(template)
  LOGGER.info("dashboard.render", produto_id=produto.id)
  return HTMLResponse(html)


@router.get("/dashboard/global/report")
def download_global_report() -> HTMLResponse:
  """Retorna instruções para gerar relatório com o modelo global."""

  content = (
    "<h2>Relatório global indisponível</h2>"
    "<p>O pipeline Prophet foi substituído pelo modelo LightGBM. Utilize o endpoint `/ml/retrain/global` para métricas atualizadas e acompanhe as previsões neste dashboard.</p>"
  )
  return HTMLResponse(content, status_code=200)


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
      "is_synthetic": [bool(registro.is_synthetic) for registro in precos],
    }
  ).sort_values("ds")
  return frame


def _empty_chart_payload() -> Dict[str, List[Optional[float]]]:
  return {
    "labels": [],
    "real_history": [],
    "synthetic_history": [],
    "forecast": [],
  }


def _load_global_forecast() -> Optional[GlobalDashboardContext]:
  with Session(engine) as session:
    produtos = list(session.exec(select(Produto.sku).order_by(Produto.sku)))

  if not produtos:
    return None

  skus = [sku for (sku,) in produtos]

  try:
    forecasts = predict_prices(skus=skus, horizon_days=DEFAULT_HORIZON_DAYS)
  except Exception as exc:
    LOGGER.warning("dashboard.global.forecast_failure", error=str(exc))
    return None

  labels: List[str] = []
  forecast_values: List[Optional[float]] = []

  base_date = datetime.now().date()
  for day_offset in range(DEFAULT_HORIZON_DAYS):
    label = (base_date + timedelta(days=day_offset + 1)).strftime("%Y-%m-%d")
    aggregated: List[float] = []
    for sku in skus:
      sku_forecasts = forecasts.get(sku, [])
      if day_offset < len(sku_forecasts):
        aggregated.append(sku_forecasts[day_offset])
    if aggregated:
      labels.append(label)
      forecast_values.append(round(float(sum(aggregated) / len(aggregated)), 4))

  if not labels:
    return None

  chart_payload = {
    "labels": labels,
    "real_history": [None] * len(labels),
    "synthetic_history": [None] * len(labels),
    "forecast": forecast_values,
  }

  metrics, trained_at, holdout_days = _fetch_global_metadata()

  return GlobalDashboardContext(
    chart_payload=chart_payload,
    metricas=metrics,
    treinado_em=trained_at or datetime.now(),
    holdout_dias=holdout_days,
    report_path=None,
  )


def _create_empty_forecast_payload(
  labels: List[str], 
  real_series: List[Optional[float]],
  synthetic_series: List[Optional[float]],
) -> Dict[str, List[Optional[float]]]:
  """Create payload with no forecast data."""

  return {
    "labels": labels,
    "real_history": real_series,
    "synthetic_history": synthetic_series,
    "forecast": [None] * len(labels),
  }


def _build_product_chart_payload(
  *, produto: Produto, history_frame: pd.DataFrame, horizon: int
) -> Tuple[Dict[str, List[Optional[float]]], Dict[str, float], datetime]:
  labels, real_series, synthetic_series = _extract_history_data(history_frame)
  if not labels:
    return _empty_chart_payload(), {}, datetime.now()

  try:
    forecasts = predict_prices(skus=[produto.sku], horizon_days=horizon)
  except Exception as exc:
    LOGGER.warning("dashboard.forecast_failure", produto_id=produto.id, error=str(exc))
    return _create_empty_forecast_payload(labels, real_series, synthetic_series), {}, datetime.now()

  forecast_values = forecasts.get(produto.sku, [])
  future_labels = _future_labels(labels[-1], len(forecast_values))
  forecast_map = {label: round(value, 4) for label, value in zip(future_labels, forecast_values)}

  chart_payload = _merge_history_and_forecast(labels, real_series, synthetic_series, forecast_map)
  metricas, treinado_em, _ = _fetch_global_metadata()
  return chart_payload, metricas, treinado_em


def _future_labels(start_label: str, horizon: int) -> List[str]:
  start_date = datetime.strptime(start_label, "%Y-%m-%d").date()
  return [
    (start_date + timedelta(days=index + 1)).strftime("%Y-%m-%d")
    for index in range(horizon)
  ]


def _merge_history_and_forecast(
  labels: List[str], 
  real_series: List[Optional[float]], 
  synthetic_series: List[Optional[float]],
  forecast_data: Dict[str, float]
) -> Dict[str, List[Optional[float]]]:
  """Merge historical data with forecast predictions."""

  all_labels = sorted(set(labels + list(forecast_data.keys())))

  real_map = {label: value for label, value in zip(labels, real_series)}
  synthetic_map = {label: value for label, value in zip(labels, synthetic_series)}

  merged_real = [real_map.get(label) for label in all_labels]
  merged_synthetic = [synthetic_map.get(label) for label in all_labels]
  merged_forecast = [forecast_data.get(label) for label in all_labels]

  return {
    "labels": all_labels,
    "real_history": merged_real,
    "synthetic_history": merged_synthetic,
    "forecast": merged_forecast,
  }


def _fetch_global_metadata() -> Tuple[Dict[str, float], Optional[datetime], int]:
  metadata_path = ROOT_DIR / "models" / "global_lgbm_metadata.json"
  if not metadata_path.is_file():
    return {}, None, 0

  try:
    payload = json.loads(metadata_path.read_text(encoding="utf-8"))
  except (OSError, json.JSONDecodeError) as exc:
    LOGGER.warning("dashboard.global.metadata_invalid", error=str(exc))
    return {}, None, 0

  metrics = {key: float(value) for key, value in (payload.get("metrics", {}) or {}).items()}

  trained_at_raw = payload.get("trained_at")
  trained_at: Optional[datetime]
  try:
    trained_at = datetime.fromisoformat(trained_at_raw) if trained_at_raw else None
  except ValueError:
    trained_at = None

  holdout_days = int(payload.get("holdout_days", 0)) if payload.get("holdout_days") is not None else 0

  return metrics, trained_at, holdout_days


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
  .global-overview { margin-top: 32px; padding-top: 24px; border-top: 1px solid #e2e8f0; }
  .global-overview h2 { margin: 0 0 12px; font-size: 1.35rem; }
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
  global_section = ""
  if template_data.get("global_available") == "true":
    global_section = f"""
    <div class="global-overview">
      <h2>Visão Geral do Catálogo</h2>
      <div class="metrics">{template_data['global_metricas_html']}</div>
      <div class="metrics">{template_data['global_holdout_text']}</div>
      <div class="metrics">{template_data['global_treino_texto']}</div>
      <div class="metrics">{template_data['global_report_text']}</div>
      <canvas id="globalPriceChart" height="110"></canvas>
    </div>
    """

  return f"""
  <section>
  {template_data['search_notice_html']}
  <canvas id="priceChart" height="120"></canvas>
  {template_data['aviso_html']}
  {global_section}
  </section>
  """


def _build_footer_section() -> str:
  """Build the footer section."""
  return f"""
  <footer>
  Horizonte de previsão: {FORECAST_HORIZON_DAYS} dias. Fonte real: Mercado Livre (ScraperAPI). Histórico sintético exibido apenas como contextualização.
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
      label: 'Histórico (real)',
      data: chartData.real_history,
      borderColor: '#2563eb',
      backgroundColor: 'rgba(37,99,235,0.15)',
      tension: 0.2,
      spanGaps: true,
      borderWidth: 2,
      pointRadius: 3,
      pointBackgroundColor: '#2563eb',
      }},
      {{
      label: 'Histórico (sintético)',
      data: chartData.synthetic_history,
      borderColor: '#ef4444',
      backgroundColor: 'rgba(239,68,68,0.15)',
      borderDash: [6,3],
      tension: 0.2,
      spanGaps: true,
      borderWidth: 2,
      pointRadius: 2,
      pointBackgroundColor: '#ef4444',
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

  const globalData = {template_data['global_chart_json']};
  if (globalData && globalData.labels) {{
    const globalCtx = document.getElementById('globalPriceChart');
    if (globalCtx) {{
      new Chart(globalCtx, {{
        type: 'line',
        data: {{
          labels: globalData.labels,
          datasets: [
            {{
              label: 'Histórico Global',
              data: globalData.real_history,
              borderColor: '#0f766e',
              backgroundColor: 'rgba(15,118,110,0.15)',
              tension: 0.2,
              spanGaps: true,
              borderWidth: 2,
              pointRadius: 2,
            }},
            {{
              label: 'Previsão Global',
              data: globalData.forecast,
              borderColor: '#f97316',
              backgroundColor: 'rgba(249,115,22,0.15)',
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
            x: {{ ticks: {{ maxRotation: 45, minRotation: 45 }} }},
            y: {{ ticks: {{ callback: value => 'R$ ' + Number(value).toFixed(2) }} }},
          }},
          plugins: {{ legend: {{ position: 'bottom' }} }}
        }}
      }});
    }}
  }}
  </script>
  """


@dataclass
class GlobalDashboardContext:
  """Context data for the global aggregated model."""

  chart_payload: Dict[str, List[Optional[float]]]
  metricas: Dict[str, float]
  treinado_em: Optional[datetime]
  holdout_dias: int
  report_path: Optional[str]


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
    global_context: Optional[GlobalDashboardContext]


def _prepare_template_data(template_data: TemplateData) -> Dict[str, str]:
  """Prepare all template data for rendering."""

  prepared: Dict[str, str] = {
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

  if template_data.global_context:
    global_ctx = template_data.global_context
    prepared.update(
      {
        "global_available": "true",
        "global_chart_json": json.dumps(global_ctx.chart_payload, ensure_ascii=False),
        "global_metricas_html": _format_metrics(global_ctx.metricas),
        "global_treino_texto": _format_training_date(global_ctx.treinado_em),
        "global_holdout_text": f"Dias em holdout: {global_ctx.holdout_dias}",
        "global_report_text": (
          f"<a href='/dashboard/global/report' target='_blank' rel='noopener'>Baixar relatório ({Path(global_ctx.report_path).name})</a>"
          if global_ctx.report_path
          else ""
        ),
      }
    )
  else:
    prepared.update(
      {
        "global_available": "false",
        "global_chart_json": "null",
        "global_metricas_html": "MSE: N/D | RMSE: N/D",
        "global_treino_texto": "Treinamento ainda não executado",
        "global_holdout_text": "",
        "global_report_text": "",
      }
    )

  return prepared


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
