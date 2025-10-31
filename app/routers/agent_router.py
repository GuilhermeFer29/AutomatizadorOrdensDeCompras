"""Rotas para execução do fluxo de agentes de cadeia de suprimentos."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.services.agent_service import run_purchase_analysis

router = APIRouter(prefix="/agents", tags=["agents"])


@router.post("/execute-analysis/{sku}")
def execute_analysis(
    sku: str,
    inquiry_reason: Optional[str] = Query(default=None, description="Contexto opcional da requisição"),
) -> dict:
    """Dispara a análise colaborativa dos agentes para o SKU informado."""

    try:
        result = run_purchase_analysis(sku=sku, inquiry_reason=inquiry_reason)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001 - propagar erro interno com status 500
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return result
