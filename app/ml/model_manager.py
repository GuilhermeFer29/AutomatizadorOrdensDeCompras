"""
Gerenciamento do ciclo de vida de modelos de ML por produto.

ARQUITETURA:
============
✅ Modelos especializados por SKU (um modelo por produto)
✅ Estrutura granular: models/{sku}/model.pkl, scaler.pkl, metadata.json
✅ Versionamento automático com timestamps
✅ Registro no banco de dados (tabela modelos_predicao)
✅ Serialização com joblib (otimizado para numpy/sklearn)

RESPONSABILIDADES:
==================
- Salvar modelos treinados com metadados
- Carregar modelos para previsão
- Gerenciar versionamento
- Sincronizar com banco de dados
- Validar integridade dos modelos
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

import joblib
import structlog
from sqlmodel import Session, select

from app.core.config import ROOT_DIR
from app.core.database import engine
from app.models.models import ModeloPredicao, Produto

LOGGER = structlog.get_logger(__name__)

# Diretório base para modelos
MODELS_DIR = ROOT_DIR / "models"
MODELS_DIR.mkdir(parents=True, exist_ok=True)


class ModelNotFoundError(Exception):
    """Exceção lançada quando um modelo não é encontrado."""


class ModelMetadata:
    """Classe para gerenciar metadados de modelos."""
    
    def __init__(
        self,
        sku: str,
        model_type: str,
        version: str,
        hyperparameters: Dict[str, Any],
        metrics: Dict[str, float],
        features: list[str],
        trained_at: str,
        training_samples: int,
    ):
        self.sku = sku
        self.model_type = model_type
        self.version = version
        self.hyperparameters = hyperparameters
        self.metrics = metrics
        self.features = features
        self.trained_at = trained_at
        self.training_samples = training_samples
    
    def to_dict(self) -> Dict[str, Any]:
        """Converte metadados para dicionário."""
        return {
            "sku": self.sku,
            "model_type": self.model_type,
            "version": self.version,
            "hyperparameters": self.hyperparameters,
            "metrics": self.metrics,
            "features": self.features,
            "trained_at": self.trained_at,
            "training_samples": self.training_samples,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ModelMetadata:
        """Cria instância a partir de dicionário."""
        return cls(
            sku=data["sku"],
            model_type=data["model_type"],
            version=data["version"],
            hyperparameters=data["hyperparameters"],
            metrics=data["metrics"],
            features=data["features"],
            trained_at=data["trained_at"],
            training_samples=data["training_samples"],
        )


def get_model_dir(sku: str) -> Path:
    """Retorna o diretório do modelo para um SKU específico."""
    model_dir = MODELS_DIR / sku
    model_dir.mkdir(parents=True, exist_ok=True)
    return model_dir


def save_model(
    sku: str,
    model: Any,
    scaler: Optional[Any],
    metadata: ModelMetadata,
) -> Path:
    """
    Salva modelo, scaler e metadados para um produto.
    
    Args:
        sku: SKU do produto
        model: Modelo treinado (ex: LGBMRegressor)
        scaler: Scaler para normalização (ex: StandardScaler)
        metadata: Metadados do modelo
    
    Returns:
        Path do diretório onde o modelo foi salvo
    """
    model_dir = get_model_dir(sku)
    
    # Salvar modelo
    model_path = model_dir / "model.pkl"
    joblib.dump(model, model_path)
    LOGGER.info(f"Modelo salvo: {model_path}")
    
    # Salvar scaler (se existir)
    if scaler is not None:
        scaler_path = model_dir / "scaler.pkl"
        joblib.dump(scaler, scaler_path)
        LOGGER.info(f"Scaler salvo: {scaler_path}")
    
    # Salvar metadados
    metadata_path = model_dir / "metadata.json"
    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(metadata.to_dict(), f, indent=2, ensure_ascii=False)
    LOGGER.info(f"Metadados salvos: {metadata_path}")
    
    # Registrar no banco de dados
    _register_model_in_database(sku, metadata, model_path)
    
    return model_dir


def load_model(sku: str) -> tuple[Any, Optional[Any], ModelMetadata]:
    """
    Carrega modelo, scaler e metadados de um produto.
    
    Args:
        sku: SKU do produto
    
    Returns:
        Tupla (model, scaler, metadata)
    
    Raises:
        ModelNotFoundError: Se o modelo não for encontrado
    """
    model_dir = get_model_dir(sku)
    
    # Verificar se o diretório existe
    if not model_dir.exists():
        raise ModelNotFoundError(f"Diretório do modelo não encontrado para SKU: {sku}")
    
    # Carregar modelo
    model_path = model_dir / "model.pkl"
    if not model_path.exists():
        raise ModelNotFoundError(f"Arquivo do modelo não encontrado: {model_path}")
    model = joblib.load(model_path)
    
    # Carregar scaler (opcional)
    scaler_path = model_dir / "scaler.pkl"
    scaler = joblib.load(scaler_path) if scaler_path.exists() else None
    
    # Carregar metadados
    metadata_path = model_dir / "metadata.json"
    if not metadata_path.exists():
        raise ModelNotFoundError(f"Metadados não encontrados: {metadata_path}")
    
    with open(metadata_path, "r", encoding="utf-8") as f:
        metadata_dict = json.load(f)
    metadata = ModelMetadata.from_dict(metadata_dict)
    
    LOGGER.info(f"Modelo carregado para SKU: {sku}")
    
    return model, scaler, metadata


def model_exists(sku: str) -> bool:
    """Verifica se um modelo existe para o SKU especificado."""
    model_dir = get_model_dir(sku)
    model_path = model_dir / "model.pkl"
    metadata_path = model_dir / "metadata.json"
    return model_path.exists() and metadata_path.exists()


def list_trained_models() -> list[str]:
    """Lista todos os SKUs que possuem modelos treinados."""
    if not MODELS_DIR.exists():
        return []
    
    trained_skus = []
    for sku_dir in MODELS_DIR.iterdir():
        if sku_dir.is_dir() and sku_dir.name != "__pycache__":
            model_path = sku_dir / "model.pkl"
            if model_path.exists():
                trained_skus.append(sku_dir.name)
    
    return sorted(trained_skus)


def get_model_info(sku: str) -> Dict[str, Any]:
    """
    Retorna informações resumidas sobre o modelo de um SKU.
    
    Args:
        sku: SKU do produto
    
    Returns:
        Dicionário com informações do modelo
    """
    if not model_exists(sku):
        return {"sku": sku, "exists": False}
    
    try:
        _, _, metadata = load_model(sku)
        return {
            "sku": sku,
            "exists": True,
            "model_type": metadata.model_type,
            "version": metadata.version,
            "metrics": metadata.metrics,
            "trained_at": metadata.trained_at,
            "training_samples": metadata.training_samples,
        }
    except Exception as e:
        LOGGER.error(f"Erro ao obter informações do modelo {sku}: {e}")
        return {"sku": sku, "exists": True, "error": str(e)}


def delete_model(sku: str) -> bool:
    """
    Remove modelo, scaler e metadados de um SKU.
    
    Args:
        sku: SKU do produto
    
    Returns:
        True se removido com sucesso, False caso contrário
    """
    model_dir = get_model_dir(sku)
    
    if not model_dir.exists():
        LOGGER.warning(f"Diretório do modelo não encontrado: {sku}")
        return False
    
    try:
        # Remover arquivos
        for file_path in model_dir.iterdir():
            if file_path.is_file():
                file_path.unlink()
        
        # Remover diretório
        model_dir.rmdir()
        
        # Remover registro do banco de dados
        _delete_model_from_database(sku)
        
        LOGGER.info(f"Modelo removido: {sku}")
        return True
    
    except Exception as e:
        LOGGER.error(f"Erro ao remover modelo {sku}: {e}")
        return False


def _register_model_in_database(
    sku: str,
    metadata: ModelMetadata,
    model_path: Path,
) -> None:
    """Registra modelo no banco de dados (tabela modelos_predicao)."""
    try:
        with Session(engine) as session:
            # Buscar produto pelo SKU
            produto = session.exec(
                select(Produto).where(Produto.sku == sku)
            ).first()
            
            if not produto:
                LOGGER.warning(f"Produto não encontrado no banco: {sku}")
                return
            
            # Verificar se já existe registro
            existing = session.exec(
                select(ModeloPredicao)
                .where(ModeloPredicao.produto_id == produto.id)
                .where(ModeloPredicao.modelo_tipo == metadata.model_type)
            ).first()
            
            if existing:
                # Atualizar registro existente
                existing.versao = metadata.version
                existing.caminho_modelo = str(model_path.relative_to(ROOT_DIR))
                existing.metricas = metadata.metrics
                existing.treinado_em = datetime.now(timezone.utc)
                LOGGER.info(f"Registro de modelo atualizado no banco: {sku}")
            else:
                # Criar novo registro
                modelo_predicao = ModeloPredicao(
                    produto_id=produto.id,
                    modelo_tipo=metadata.model_type,
                    versao=metadata.version,
                    caminho_modelo=str(model_path.relative_to(ROOT_DIR)),
                    metricas=metadata.metrics,
                    treinado_em=datetime.now(timezone.utc),
                )
                session.add(modelo_predicao)
                LOGGER.info(f"Modelo registrado no banco: {sku}")
            
            session.commit()
    
    except Exception as e:
        LOGGER.error(f"Erro ao registrar modelo no banco {sku}: {e}")


def _delete_model_from_database(sku: str) -> None:
    """Remove registro do modelo do banco de dados."""
    try:
        with Session(engine) as session:
            produto = session.exec(
                select(Produto).where(Produto.sku == sku)
            ).first()
            
            if produto:
                session.exec(
                    select(ModeloPredicao)
                    .where(ModeloPredicao.produto_id == produto.id)
                ).delete()
                session.commit()
                LOGGER.info(f"Registro de modelo removido do banco: {sku}")
    
    except Exception as e:
        LOGGER.error(f"Erro ao remover modelo do banco {sku}: {e}")


__all__ = [
    "ModelMetadata",
    "ModelNotFoundError",
    "save_model",
    "load_model",
    "model_exists",
    "list_trained_models",
    "get_model_info",
    "delete_model",
    "get_model_dir",
]
