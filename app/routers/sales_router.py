"""Routes dedicated to sales ingestion and model retraining triggers."""

from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel

from app.services.sales_ingestion_service import ingest_sales_dataframe, load_sales_dataframe
# Nota: Treinamento de modelos agora é por produto via /ml/train/{sku}

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

        # Nota: Treinamento agora é manual via endpoint /ml/train/{sku}
        response = SalesUploadResponse(
            produtos=produto_ids,
            task_id="manual_training_required",
            mensagem=(
                f"Dados de vendas importados com sucesso para {len(produto_ids)} produtos. "
                "Use o endpoint /ml/train/{{sku}} para treinar modelos individuais."
            ),
        )
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
    finally:
        await arquivo.close()

    return response


@router.post("/retrain/{produto_id}", status_code=status.HTTP_202_ACCEPTED)
def retrain_model(produto_id: int) -> dict:
    """Endpoint descontinuado. Use /ml/train/{sku} para treinar modelos individuais."""
    return {
        "produto_id": produto_id,
        "task_id": None,
        "mensagem": "Este endpoint foi descontinuado. Use POST /ml/train/{{sku}} para treinar modelos por produto.",
        "deprecated": True,
    }
