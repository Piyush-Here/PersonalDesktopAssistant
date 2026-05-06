from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class RequestMode(str, Enum):
    ASK = "ask"
    PREPARE = "prepare"
    ACT = "act"


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class StepStatus(str, Enum):
    PENDING = "pending"
    READY = "ready"
    COMPLETED = "completed"
    BLOCKED = "blocked"
    FAILED = "failed"


class UserRequest(BaseModel):
    text: str = Field(min_length=1, max_length=2000)
    mode: RequestMode = RequestMode.ACT


class PlanStep(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    description: str
    tool: str
    target: str
    risk_level: RiskLevel
    requires_confirmation: bool
    status: StepStatus = StepStatus.PENDING
    preview: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class Plan(BaseModel):
    summary: str
    steps: list[PlanStep]
    requires_confirmation: bool


class ExecutionResult(BaseModel):
    success: bool
    message: str
    details: list[str] = Field(default_factory=list)


class ActionSession(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    created_at: datetime = Field(default_factory=datetime.utcnow)
    request: UserRequest
    plan: Plan
    observations: list[str] = Field(default_factory=list)
    confirmed: bool = False
    execution_result: ExecutionResult | None = None


class AssistantReply(BaseModel):
    session_id: str
    mode: RequestMode
    summary: str
    observations: list[str] = Field(default_factory=list)
    plan: Plan
    execution_result: ExecutionResult | None = None


class ConfirmationRequest(BaseModel):
    session_id: str
    approved: bool
