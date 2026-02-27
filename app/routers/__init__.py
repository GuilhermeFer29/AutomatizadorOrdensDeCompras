"""API routers grouping application endpoints."""

from app.routers import (  # noqa: F401 – re-export for `from app.routers import X`
    admin_router,
    agent_router,
    api_agent_router,
    api_audit_router,
    api_chat_router,
    api_dashboard_router,
    api_order_router,
    api_product_router,
    api_supplier_router,
    auth_router,
    ml_router,
    rag_router,
    sales_router,
    tasks_router,
)
