"""API routes for task orchestration and monitoring."""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Body, HTTPException, status
from pydantic import BaseModel, Field

from app.services.task_service import get_task_status, trigger_long_running_task

router = APIRouter(prefix="/tasks", tags=["tasks"])


class TaskRequest(BaseModel):
    """Payload to enqueue a debug task."""

    duration_seconds: int = Field(default=5, ge=0, le=3600)


class TaskResponse(BaseModel):
    """Response carrying the enqueued task ID."""

    task_id: str


class TaskStatusResponse(BaseModel):
    """Response detailing the task processing status."""

    task_id: str
    state: str
    result: Optional[Any] = None


@router.post("/test", response_model=TaskResponse, status_code=status.HTTP_202_ACCEPTED)
def enqueue_test_task(payload: TaskRequest = Body(default=TaskRequest())) -> TaskResponse:
    """Enqueue the debug task and return its identifier."""
    async_result = trigger_long_running_task(duration_seconds=payload.duration_seconds)
    return TaskResponse(task_id=async_result.id)


@router.get("/{task_id}", response_model=TaskStatusResponse)
def fetch_task_status(task_id: str) -> TaskStatusResponse:
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
