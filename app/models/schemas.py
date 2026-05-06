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
    risk_score: int = Field(default=0, ge=0, le=100)
    risk_reasons: list[str] = Field(default_factory=list)
    requires_confirmation: bool
    status: StepStatus = StepStatus.PENDING
    preview: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class RiskAssessment(BaseModel):
    score: int = Field(ge=0, le=100)
    level: RiskLevel
    requires_confirmation: bool
    reasons: list[str] = Field(default_factory=list)


class Plan(BaseModel):
    summary: str
    steps: list[PlanStep]
    requires_confirmation: bool
    risk_assessment: RiskAssessment


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
