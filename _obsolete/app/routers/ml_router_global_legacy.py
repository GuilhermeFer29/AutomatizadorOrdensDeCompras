"""Rotas para treinamento e previsão de modelos ML por produto.

ARQUITETURA NOVA (2025-10-16):
===============================
✅ POST /ml/train/{sku} - Treinar modelo para um produto específico
✅ GET /ml/predict/{sku} - Obter previsões para um produto
✅ GET /ml/models - Listar todos os modelos treinados
✅ GET /ml/models/{sku} - Informações de um modelo específico
✅ DELETE /ml/models/{sku} - Remover modelo de um produto
"""

from __future__ import annotations

from typing import Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.ml.model_manager import (
    ModelNotFoundError,
    delete_model,
    get_model_info,
    list_trained_models,
)
from app.ml.prediction import InsufficientHistoryError, predict_prices_for_product
from app.ml.training import train_model_for_product

router = APIRouter(prefix="/ml", tags=["ml"])


# ============================================================================
# RESPONSE MODELS
# ============================================================================

class TrainResponse(BaseModel):
    """Resposta do treinamento de modelo."""
    
    sku: str
    success: bool
    metrics: Dict[str, float]
    training_samples: int
    validation_samples: int
    features_count: int
    message: str = "Modelo treinado com sucesso"


class PredictionResponse(BaseModel):
    """Resposta contendo previsões de preços."""
    
    sku: str
    dates: List[str]
    prices: List[float]
    model_used: str
    metrics: Optional[Dict[str, float]] = None


class ModelInfoResponse(BaseModel):
    """Informações sobre um modelo treinado."""
    
    sku: str
    exists: bool
    model_type: Optional[str] = None
    version: Optional[str] = None
    metrics: Optional[Dict[str, float]] = None
    trained_at: Optional[str] = None
    training_samples: Optional[int] = None


class ModelsListResponse(BaseModel):
    """Lista de modelos treinados."""
    
    models: List[str]
    count: int


# ============================================================================
# ENDPOINTS
# ============================================================================

@router.post(
    "/train/{sku}",
    response_model=TrainResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Treinar modelo para um produto",
)
def train_product_model(
    sku: str,
    optimize: bool = Query(True, description="Otimizar hiperparâmetros com Optuna"),
    n_trials: int = Query(50, ge=10, le=200, description="Número de trials Optuna"),
) -> TrainResponse:
    """
    Treina um modelo LightGBM especializado para o produto especificado.
    
    - **sku**: SKU do produto
    - **optimize**: Se True, otimiza hiperparâmetros (mais lento mas melhor)
    - **n_trials**: Número de iterações para otimização Optuna
    """
    try:
        result = train_model_for_product(sku=sku, optimize=optimize, n_trials=n_trials)
        return TrainResponse(**result)
    
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao treinar modelo: {str(e)}",
        )


@router.get(
    "/predict/{sku}",
    response_model=PredictionResponse,
    summary="Obter previsões de preços",
)
def predict_product_prices(
    sku: str,
    days_ahead: int = Query(14, ge=1, le=60, description="Dias à frente para prever"),
) -> PredictionResponse:
    """
    Retorna previsões autorregressivas de preços para o produto.
    
    - **sku**: SKU do produto
    - **days_ahead**: Número de dias futuros para prever (1-60)
    """
    try:
        result = predict_prices_for_product(sku=sku, days_ahead=days_ahead)
        
        if "error" in result:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result["error"],
            )
        
        return PredictionResponse(**result)
    
    except InsufficientHistoryError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao gerar previsão: {str(e)}",
        )


@router.get(
    "/models",
    response_model=ModelsListResponse,
    summary="Listar modelos treinados",
)
def list_models() -> ModelsListResponse:
    """Lista todos os SKUs que possuem modelos treinados."""
    models = list_trained_models()
    return ModelsListResponse(models=models, count=len(models))


@router.get(
    "/models/{sku}",
    response_model=ModelInfoResponse,
    summary="Informações de um modelo",
)
def get_model_details(sku: str) -> ModelInfoResponse:
    """Retorna informações detalhadas sobre o modelo de um produto."""
    info = get_model_info(sku)
    return ModelInfoResponse(**info)


@router.delete(
    "/models/{sku}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remover modelo",
)
def remove_model(sku: str):\n    """
    Remove o modelo treinado de um produto.
    
    Útil para forçar re-treinamento ou limpar modelos obsoletos.
    """
    success = delete_model(sku)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Modelo não encontrado para SKU: {sku}",
        )
    
    return None
