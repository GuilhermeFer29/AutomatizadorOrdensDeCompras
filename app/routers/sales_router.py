"""Routes dedicated to sales ingestion and model retraining triggers."""

from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel

from app.services.sales_ingestion_service import ingest_sales_dataframe, load_sales_dataframe
from app.services.task_service import trigger_retrain_model_task

router = APIRouter(prefix="/vendas", tags=["vendas"])


class RetrainTaskInfo(BaseModel):
    """Metadata for a scheduled retraining task."""

    produto_id: int
    task_id: str


class SalesUploadResponse(BaseModel):
    """Response returned after processing a CSV upload of sales data."""

    produtos: List[int]
    tarefas: List[RetrainTaskInfo]


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

        tarefas = [
            RetrainTaskInfo(
                produto_id=produto_id,
                task_id=trigger_retrain_model_task(
                    produto_id=produto_id,
                    destinatario_email=destinatario_email,
                ).id,
            )
            for produto_id in produto_ids
        ]

        response = SalesUploadResponse(produtos=produto_ids, tarefas=tarefas)
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
    finally:
        await arquivo.close()

    return response
