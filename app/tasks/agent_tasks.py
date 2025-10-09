"""
Tarefas Celery para execução assíncrona de análises de agentes.

CORREÇÕES APLICADAS:
- Atualizado para usar a nova função run_supply_chain_analysis() da API moderna do Agno
- Mantida compatibilidade com execute_supply_chain_analysis() do agent_service.py
"""

from app.core.celery_app import celery_app
import structlog

LOGGER = structlog.get_logger(__name__)

@celery_app.task(name="execute_agent_analysis")
def execute_agent_analysis_task(sku: str):
    """
    Tarefa Celery para executar análise de cadeia de suprimentos usando Agno Team.
    
    Esta tarefa delega para agent_service.execute_supply_chain_analysis(),
    que por sua vez usa a nova implementação Agno com API moderna.
    
    Args:
        sku: SKU do produto a ser analisado
        
    Returns:
        Dict com o resultado da análise completa
    """
    from app.services.agent_service import execute_supply_chain_analysis
    
    LOGGER.info("agents.task.start", sku=sku)
    try:
        result = execute_supply_chain_analysis(sku=sku)
        LOGGER.info("agents.task.completed", sku=sku, decision=result.get("recommendation", {}).get("decision"))
        return result
    except Exception as e:
        LOGGER.error("agents.task.failed", sku=sku, error=str(e))
        raise
