"""Routes to orchestrate ML retraining workflows via Celery."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Body, status
from pydantic import BaseModel, EmailStr

from app.services.task_service import trigger_retrain_model_task

router = APIRouter(prefix="/vendas", tags=["ml"])


class RetrainRequest(BaseModel):
    """Optional payload extending the retraining request."""

    email: Optional[EmailStr] = None


class RetrainResponse(BaseModel):
    """Response structure exposing the Celery task identifier."""

    task_id: str
    produto_id: int


@router.post(
    "/retrain/{produto_id}",
    response_model=RetrainResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def enqueue_retrain(produto_id: int, payload: RetrainRequest = Body(default=RetrainRequest())) -> RetrainResponse:
    """Dispatch the Prophet retraining flow for a specific product."""

    async_result = trigger_retrain_model_task(
        produto_id=produto_id,
        destinatario_email=payload.email,
    )
    return RetrainResponse(task_id=async_result.id, produto_id=produto_id)
