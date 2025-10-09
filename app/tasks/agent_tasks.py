from app.core.celery_app import celery_app
import structlog

LOGGER = structlog.get_logger(__name__)

@celery_app.task(name="execute_agent_analysis")
def execute_agent_analysis_task(sku: str):
    """Celery task to run the supply chain analysis for a given SKU."""
    from app.services.agent_service import execute_supply_chain_analysis
    LOGGER.info("Starting agent analysis task for SKU: %s", sku)
    try:
        result = execute_supply_chain_analysis(sku=sku)
        LOGGER.info("Agent analysis task completed for SKU: %s", sku, result=result)
        # O resultado poderia ser salvo no banco de dados ou enviado para outro serviço
        return result
    except Exception as e:
        LOGGER.error("Agent analysis task failed for SKU: %s", sku, error=str(e))
        raise
