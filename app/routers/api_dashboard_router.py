from fastapi import APIRouter, Depends
from sqlmodel import Session
from app.core.database import get_session
from app.services.dashboard_service import get_dashboard_kpis, get_dashboard_alerts

router = APIRouter(prefix="/api/dashboard", tags=["api-dashboard"])

@router.get("/kpis")
def read_dashboard_kpis(session: Session = Depends(get_session)):
    return get_dashboard_kpis(session)

@router.get("/alerts")
def read_dashboard_alerts(session: Session = Depends(get_session)):
    return get_dashboard_alerts(session)
