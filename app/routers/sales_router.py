"""Routes dedicated to sales ingestion and model retraining triggers."""

from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel

from app.services.sales_ingestion_service import ingest_sales_dataframe, load_sales_dataframe
from app.services.task_service import trigger_retrain_global_model_task

router = APIRouter(prefix="/vendas", tags=["vendas"])


class SalesUploadResponse(BaseModel):
    """Response returned after processing a CSV upload of sales data."""

    produtos: List[int]
    task_id: str
    mensagem: str


@router.post("/upload", response_model=SalesUploadResponse, status_code=status.HTTP_202_ACCEPTED)
async def upload_sales_csv(
    arquivo: UploadFile = File(...),
    destinatario_email: Optional[str] = Form(default=None),
) -> SalesUploadResponse:
    """Persist a CSV file with sales data and trigger model retraining for affected products."""

    if arquivo.content_type not in {"text/csv", "application/vnd.ms-excel", "application/octet-stream"}:
        await arquivo.close()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Apenas arquivos CSV são aceitos.")

    try:
        dataframe = load_sales_dataframe(arquivo.file)
        produto_ids = ingest_sales_dataframe(dataframe=dataframe)

        if not produto_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Nenhum registro válido foi encontrado no arquivo enviado.",
            )

        async_result = trigger_retrain_global_model_task()
        response = SalesUploadResponse(
            produtos=produto_ids,
            task_id=async_result.id,
            mensagem=(
                "Treinamento global LightGBM agendado. Modelos individuais foram substituídos pelo fluxo global."
            ),
        )
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
    finally:
        await arquivo.close()

    return response


@router.post("/retrain/{produto_id}", status_code=status.HTTP_202_ACCEPTED)
def retrain_model(produto_id: int) -> dict:
    """Trigger retraining for a specific product."""
    async_result = trigger_retrain_global_model_task()
    return {
        "produto_id": produto_id,
        "task_id": async_result.id,
        "mensagem": "Treinamento global acionado. Modelos Prophet individuais foram descontinuados.",
    }
