from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session
from app.core.database import get_session
from app.services.agent_service import get_agents, toggle_agent_status, run_agent_now

router = APIRouter(prefix="/api/agents", tags=["api-agents"])

@router.get("/")
def read_agents(session: Session = Depends(get_session)):
    return get_agents(session)

@router.post("/{agent_id}/{action}")
def handle_agent_action(agent_id: int, action: str, session: Session = Depends(get_session)):
    if action not in ["pause", "activate", "run"]:
        raise HTTPException(status_code=400, detail="Invalid action")
    
    if action == "run":
        agent = run_agent_now(session, agent_id)
    else:
        agent = toggle_agent_status(session, agent_id, action)
        
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent
