"""API routes for task orchestration and monitoring."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.core.security import get_current_user
from app.services.task_service import get_task_status

router = APIRouter(prefix="/tasks", tags=["tasks"])


class TaskResponse(BaseModel):
    """Response carrying the enqueued task ID."""

    task_id: str


class TaskStatusResponse(BaseModel):
    """Response detailing the task processing status."""

    task_id: str
    state: str
    result: Any | None = None


@router.get("/{task_id}", response_model=TaskStatusResponse)
def fetch_task_status(task_id: str, current_user=Depends(get_current_user)) -> TaskStatusResponse:
    """Return the current state of a task by its identifier."""
    status_payload = get_task_status(task_id=task_id)
    if status_payload["state"] == "FAILURE":
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "task_id": task_id,
                "state": status_payload["state"],
                "result": status_payload.get("result"),
            },
        )
    return TaskStatusResponse(**status_payload)
