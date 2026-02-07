from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from app.core.security import get_current_user
from app.core.tenant import get_tenant_session
from app.services.agent_service import get_agents, run_agent_now, toggle_agent_status

router = APIRouter(prefix="/api/agents", tags=["api-agents"])

@router.get("/")
def read_agents(session: Session = Depends(get_tenant_session), current_user=Depends(get_current_user)):
    return get_agents(session)

@router.post("/{agent_id}/{action}")
def handle_agent_action(agent_id: int, action: str, session: Session = Depends(get_tenant_session), current_user=Depends(get_current_user)):
    if action not in ["pause", "activate", "run"]:
        raise HTTPException(status_code=400, detail="Invalid action")

    if action == "run":
        agent = run_agent_now(session, agent_id)
    else:
        agent = toggle_agent_status(session, agent_id, action)

    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent
