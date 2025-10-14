"""
Router para gerenciamento do RAG (Retrieval Augmented Generation).

Endpoints para sincronização manual e monitoramento do estado do RAG.
"""

from fastapi import APIRouter, HTTPException
from typing import Dict, Any
import logging

from app.services.rag_sync_service import rag_sync_service, trigger_rag_sync

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/rag", tags=["RAG Management"])


@router.get("/status")
async def get_rag_status() -> Dict[str, Any]:
    """
    Retorna o status atual do RAG.
    
    Returns:
        dict: Informações sobre sincronização e estado do ChromaDB
    """
    try:
        status = rag_sync_service.get_sync_status()
        return {
            "success": True,
            "data": status
        }
    except Exception as e:
        logger.error(f"Erro ao obter status do RAG: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sync")
async def sync_rag() -> Dict[str, Any]:
    """
    Força sincronização manual do RAG com o banco de dados.
    
    Limpa o ChromaDB e re-indexa todos os produtos do MySQL.
    
    Returns:
        dict: Resultado da sincronização
    """
    try:
        logger.info("📡 Sincronização manual do RAG acionada via API")
        result = trigger_rag_sync()
        
        if result["status"] == "success":
            return {
                "success": True,
                "message": "RAG sincronizado com sucesso",
                "data": result
            }
        else:
            return {
                "success": False,
                "message": result["message"],
                "data": result
            }
    except Exception as e:
        logger.error(f"Erro ao sincronizar RAG: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/resync")
async def force_resync_rag() -> Dict[str, Any]:
    """
    Força re-sincronização completa do RAG (alias para /sync).
    
    Limpa completamente o ChromaDB e reconstrói do zero.
    
    Returns:
        dict: Resultado da re-sincronização
    """
    return await sync_rag()
