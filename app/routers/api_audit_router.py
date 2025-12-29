"""
Router para Log de Auditoria de Decisões dos Agentes.

Endpoints:
- GET /api/audit/decisions/      Lista decisões recentes
- GET /api/audit/decisions/{id}  Detalhes de uma decisão
"""

from typing import Optional
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select
from sqlalchemy import desc

from app.core.database import get_session
from app.models.models import AuditoriaDecisao

router = APIRouter(prefix="/api/audit", tags=["audit"])


@router.get("/decisions/")
def list_decisions(
    limit: int = Query(default=50, ge=1, le=200),
    sku: Optional[str] = None,
    agente: Optional[str] = None,
    days: int = Query(default=30, ge=1, le=365),
    session: Session = Depends(get_session)
):
    """Lista decisões de agentes dos últimos X dias."""
    
    # Filtrar por data
    min_date = datetime.now() - timedelta(days=days)
    
    query = select(AuditoriaDecisao).where(
        AuditoriaDecisao.data_decisao >= min_date
    ).order_by(desc(AuditoriaDecisao.data_decisao))
    
    # Filtros opcionais
    if sku:
        query = query.where(AuditoriaDecisao.sku.ilike(f"%{sku}%"))
    
    if agente:
        query = query.where(AuditoriaDecisao.agente_nome.ilike(f"%{agente}%"))
    
    decisions = session.exec(query.limit(limit)).all()
    
    result = []
    for dec in decisions:
        result.append({
            "id": dec.id,
            "agente_nome": dec.agente_nome,
            "sku": dec.sku,
            "acao": dec.acao,
            "decisao_preview": dec.decisao[:200] + "..." if len(dec.decisao) > 200 else dec.decisao,
            "data_decisao": dec.data_decisao.isoformat(),
            "usuario_id": dec.usuario_id,
        })
    
    return result


@router.get("/decisions/{decision_id}")
def get_decision(
    decision_id: int,
    session: Session = Depends(get_session)
):
    """Detalhes completos de uma decisão."""
    
    decision = session.get(AuditoriaDecisao, decision_id)
    if not decision:
        raise HTTPException(status_code=404, detail="Decisão não encontrada")
    
    return {
        "id": decision.id,
        "agente_nome": decision.agente_nome,
        "sku": decision.sku,
        "acao": decision.acao,
        "decisao": decision.decisao,
        "raciocinio": decision.raciocinio,
        "contexto": decision.contexto,
        "usuario_id": decision.usuario_id,
        "data_decisao": decision.data_decisao.isoformat(),
        "ip_origem": decision.ip_origem,
    }


@router.get("/stats/")
def get_audit_stats(
    days: int = Query(default=30, ge=1, le=365),
    session: Session = Depends(get_session)
):
    """Estatísticas das decisões."""
    from sqlalchemy import func
    
    min_date = datetime.now() - timedelta(days=days)
    
    # Total de decisões
    total = session.exec(
        select(func.count(AuditoriaDecisao.id))
        .where(AuditoriaDecisao.data_decisao >= min_date)
    ).first() or 0
    
    # Decisões por agente
    decisions = session.exec(
        select(AuditoriaDecisao)
        .where(AuditoriaDecisao.data_decisao >= min_date)
    ).all()
    
    by_agent = {}
    by_action = {}
    by_sku = {}
    
    for dec in decisions:
        by_agent[dec.agente_nome] = by_agent.get(dec.agente_nome, 0) + 1
        by_action[dec.acao] = by_action.get(dec.acao, 0) + 1
        by_sku[dec.sku] = by_sku.get(dec.sku, 0) + 1
    
    return {
        "total_decisions": total,
        "period_days": days,
        "by_agent": by_agent,
        "by_action": by_action,
        "top_skus": dict(sorted(by_sku.items(), key=lambda x: x[1], reverse=True)[:10])
    }
