"""
Pipeline de Validação e Treinamento (Project Lite)
Simplificado para usar StatsForecast e AutoARIMA.

ARQUITETURA LITE:
=================
✅ StatsForecast com AutoARIMA (Zero Config)
✅ Validação de dados e disponibilidade
✅ Métricas simples de erro em tempo de execução
✅ Sem persistência de modelos pesados (pkl), apenas logs e métricas
"""

from __future__ import annotations

import logging
from typing import Dict, Any, List, Optional

import pandas as pd
import numpy as np
from statsforecast import StatsForecast
from statsforecast.models import AutoARIMA, Naive
from sqlmodel import Session, select

from app.core.database import engine
from app.models.models import Produto, VendasHistoricas
from app.ml.prediction import _load_history_as_dataframe

# Configuração de logging
LOGGER = logging.getLogger(__name__)

# Exceção para compatibilidade com imports existentes
class InsufficientDataError(Exception):
    pass

def train_model_for_product(
    sku: str,
    optimize: bool = False,
    n_trials: int = 0,
    backtest: bool = False,
    target: str = "quantidade",
    use_all_data: bool = True,
) -> Dict[str, Any]:
    """
    Versão 'Lite' do treinamento: Valida dados e testa a capacidade de previsão do StatsForecast.
    Não salva modelos pesados em disco, pois AutoARIMA é ajustado rapidamente em tempo de execução.
    
    Args:
        sku: SKU do produto
        optimize: Ignorado no modo Lite (AutoARIMA é automático)
        n_trials: Ignorado no modo Lite
        backtest: Se True, executa um cross-validation simples
        target: Mantido para compatibilidade (apenas 'quantidade' é totalmente suportado agora)
        use_all_data: Ignorado
        
    Returns:
        Dicionário com métricas e status
    """
    LOGGER.info(f"🚀 Iniciando validação ML Lite para {sku}")
    
    with Session(engine) as session:
        # 1. Carregar dados usando utilitário do prediction.py
        try:
            df = _load_history_as_dataframe(session, sku)
        except ValueError as e:
            LOGGER.error(f"Erro ao carregar dados para {sku}: {e}")
            raise
            
        if len(df) < 14:
            raise InsufficientDataError(f"Histórico insuficiente: {len(df)} dias (mínimo 14)")

        # 2. Executar validação 'backtest' se solicitado (simula treinamento)
        metrics = {}
        if backtest:
            LOGGER.info(f"Executando backtest Lite para {sku}...")
            try:
                # Definir modelos
                models = [AutoARIMA(season_length=7), Naive()]
                sf = StatsForecast(
                    models=models,
                    freq='D',
                    n_jobs=1,
                    verbose=False
                )
                
                # Cross-validation simples (últimos 7 dias)
                cross_val_df = sf.cross_validation(
                    df=df,
                    h=7,
                    step_size=7,
                    n_windows=1
                )
                
                # Calcular MAE/RMSE simples
                # cross_val_df columns: [unique_id, ds, cutoff, y, AutoARIMA, Naive]
                model_col = "AutoARIMA" if "AutoARIMA" in cross_val_df.columns else "Naive"
                
                # Garantir numérico
                y_true = cross_val_df["y"].values
                y_pred = cross_val_df[model_col].values
                
                mae = np.mean(np.abs(y_true - y_pred))
                rmse = np.sqrt(np.mean((y_true - y_pred)**2))
                
                metrics = {
                    "mae": float(mae),
                    "rmse": float(rmse),
                    "model_used": model_col
                }
                LOGGER.info(f"Backtest concluído: MAE={mae:.2f}")
                
            except Exception as e:
                LOGGER.warning(f"Falha no backtest para {sku}, prosseguindo sem métricas: {e}")
                metrics = {"error": str(e)}

        return {
            "sku": sku,
            "status": "success",
            "metrics": metrics,
            "training_samples": len(df),
            "model_type": "StatsForecast_Lite"
        }

__all__ = ["train_model_for_product", "InsufficientDataError"]
