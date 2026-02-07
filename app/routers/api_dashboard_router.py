from fastapi import APIRouter, Depends
from sqlmodel import Session

from app.core.cache import cache_response
from app.core.security import get_current_user
from app.core.tenant import get_tenant_session
from app.services.dashboard_service import get_dashboard_alerts, get_dashboard_kpis

router = APIRouter(prefix="/api/dashboard", tags=["api-dashboard"])

@router.get("/kpis")
@cache_response(namespace="dashboard")
def read_dashboard_kpis(session: Session = Depends(get_tenant_session), current_user=Depends(get_current_user)):
    return get_dashboard_kpis(session)

@router.get("/alerts")
@cache_response(namespace="dashboard")
def read_dashboard_alerts(session: Session = Depends(get_tenant_session), current_user=Depends(get_current_user)):
    return get_dashboard_alerts(session)
