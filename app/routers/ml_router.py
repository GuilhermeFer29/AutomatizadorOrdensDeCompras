"""Rotas para treinamento global LightGBM e geração de previsões."""

from __future__ import annotations

from typing import Dict, List

from fastapi import APIRouter, Query, status
from pydantic import BaseModel

from app.ml.training import predict_prices
from app.services.task_service import trigger_retrain_global_model_task

router = APIRouter(prefix="/ml", tags=["ml"])


class RetrainResponse(BaseModel):
    """Resposta contendo a identificação da tarefa Celery."""

    task_id: str


@router.post(
    "/retrain/global",
    response_model=RetrainResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def enqueue_global_retrain() -> RetrainResponse:
    """Dispara o treinamento global LightGBM."""

    async_result = trigger_retrain_global_model_task()
    return RetrainResponse(task_id=async_result.id)


class PredictionResponse(BaseModel):
    """Resposta contendo previsões por SKU."""

    forecasts: Dict[str, List[float]]


@router.get("/predict", response_model=PredictionResponse)
def get_predictions(
    sku: List[str] = Query(..., description="Lista de SKUs a serem previstos"),
    horizon_days: int = Query(14, ge=1, le=60, description="Quantidade de dias futuros"),
) -> PredictionResponse:
    """Retorna previsões do modelo global para os SKUs informados."""

    forecasts = predict_prices(skus=sku, horizon_days=horizon_days)
    return PredictionResponse(forecasts=forecasts)
