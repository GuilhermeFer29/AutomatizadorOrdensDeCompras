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

from typing import Dict, List, Optional, Any

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field
from celery.result import AsyncResult

from app.ml.model_manager import (
    ModelNotFoundError,
    delete_model,
    get_model_info,
    list_trained_models,
    list_available_targets,  # ← Novo
)
from app.ml.prediction import InsufficientHistoryError, predict_prices_for_product
from app.ml.training import train_model_for_product
from app.tasks.ml_tasks import train_product_model_task, train_all_products_task

router = APIRouter(prefix="/ml", tags=["ml"])


# ============================================================================
# RESPONSE MODELS
# ============================================================================

class AsyncTaskResponse(BaseModel):
    """Resposta da task assíncrona."""
    
    task_id: str
    status: str = "PENDING"
    message: str = "Task iniciada com sucesso"


class TaskStatusResponse(BaseModel):
    """Status da task em execução."""
    
    task_id: str
    status: str
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    traceback: Optional[str] = None
    date_done: Optional[str] = None


class TrainResponse(BaseModel):
    """Resposta do treinamento de modelo."""
    
    sku: str
    status: str
    metrics: Dict[str, float]
    training_samples: int
    validation_samples: int
    feature_count: int
    model_type: str
    version: str
    optimized: bool
    backtest_metrics: List[Dict[str, float]] = []
    training_time: str
    success: bool = True
    message: str = "Modelo treinado com sucesso"


class PredictionResponse(BaseModel):
    """Resposta contendo previsões de preços."""
    
    sku: str
    dates: List[str]
    prices: List[float]
    model_used: str
    metrics: Optional[Dict[str, float]] = None
    method: Optional[str] = None


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
    "/train/{sku}/async",
    response_model=AsyncTaskResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Treinar modelo assincronamente",
)
def train_product_model_async(
    sku: str,
    optimize: bool = Query(True, description="Otimizar hiperparâmetros com Optuna"),
    n_trials: int = Query(50, ge=10, le=200, description="Número de trials Optuna"),
) -> AsyncTaskResponse:
    """
    Inicia treinamento assíncrono de modelo para o produto especificado.
    
    Retorna imediatamente com task_id para consulta de status.
    
    - **sku**: SKU do produto
    - **optimize**: Se True, otimiza hiperparâmetros (mais lento mas melhor)
    - **n_trials**: Número de iterações para otimização Optuna
    """
    try:
        task = train_product_model_task.delay(sku=sku, optimize=optimize, n_trials=n_trials)
        return AsyncTaskResponse(
            task_id=task.id,
            status=task.status,
            message=f"Task de treinamento para {sku} iniciada"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao iniciar task: {str(e)}",
        )


@router.get(
    "/tasks/{task_id}",
    response_model=TaskStatusResponse,
    summary="Consultar status da task",
)
def get_task_status(task_id: str) -> TaskStatusResponse:
    """
    Consulta o status de uma task de treinamento.
    
    - **task_id**: ID da task retornado pelo endpoint /train/{sku}/async
    """
    try:
        result = AsyncResult(task_id)
        
        response_data = {
            "task_id": task_id,
            "status": result.status,
            "result": result.result if result.ready() else None,
            "error": str(result.info) if result.failed() else None,
            "traceback": result.traceback if result.failed() else None,
            "date_done": result.date_done.isoformat() if result.date_done else None,
        }
        
        return TaskStatusResponse(**response_data)
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao consultar task: {str(e)}",
        )


@router.post(
    "/train/all/async",
    response_model=AsyncTaskResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Treinar todos os modelos assincronamente",
)
def train_all_products_async(
    optimize: bool = Query(False, description="Otimizar hiperparâmetros"),
    limit: int = Query(None, ge=1, le=1000, description="Limite de produtos"),
) -> AsyncTaskResponse:
    """
    Inicia treinamento assíncrono de todos os produtos.
    
    - **optimize**: Se True, otimiza hiperparâmetros (muito mais lento)
    - **limit**: Número máximo de produtos para treinar
    """
    try:
        task = train_all_products_task.delay(optimize=optimize, limit=limit)
        return AsyncTaskResponse(
            task_id=task.id,
            status=task.status,
            message=f"Task de treinamento em lote iniciada (limit={limit})"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao iniciar task: {str(e)}",
        )


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
        result = train_model_for_product(sku=sku, optimize=optimize, n_trials=n_trials, backtest=True)
        
        # Mapear campos para compatibilidade
        response_data = {
            "sku": result["sku"],
            "status": result["status"],
            "metrics": result["metrics"],
            "training_samples": result["training_samples"],
            "validation_samples": result["validation_samples"],
            "feature_count": result["feature_count"],
            "model_type": result["model_type"],
            "version": result["version"],
            "optimized": result["optimized"],
            "backtest_metrics": result["backtest_metrics"],
            "training_time": result["training_time"],
            "success": result["status"] == "success",
        }
        
        return TrainResponse(**response_data)
    
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
    summary="Obter previsões (multi-target)",
)
def predict_product_prices(
    sku: str,
    target: str = Query("quantidade", description="Target para previsão: quantidade, preco, receita, lucro, margem, custo, rotatividade, dias_estoque"),
    days_ahead: int = Query(14, ge=1, le=60, description="Dias à frente para prever"),
) -> PredictionResponse:
    """
    Retorna previsões autorregressivas para um target específico.
    
    - **sku**: SKU do produto
    - **target**: Target para previsão (padrão: quantidade)
    - **days_ahead**: Número de dias futuros para prever (1-60)
    """
    try:
        result = predict_prices_for_product(sku=sku, days_ahead=days_ahead, target=target)
        
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
    "/models/{sku}/targets",
    response_model=Dict[str, Any],
    summary="Listar targets disponíveis para um SKU",
)
def get_available_targets(sku: str) -> Dict[str, Any]:
    """
    Lista todos os targets (modelos) disponíveis para um SKU.
    
    Exemplo de resposta:
    ```json
    {
        "sku": "386DC631",
        "targets": ["quantidade", "preco", "receita", "lucro", "margem"],
        "count": 5
    }
    ```
    """
    targets = list_available_targets(sku)
    return {
        "sku": sku,
        "targets": targets,
        "count": len(targets),
    }


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
def remove_model(sku: str):
    """
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
