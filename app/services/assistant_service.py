from __future__ import annotations

from pathlib import Path

from app.core.intent import infer_mode
from app.core.planner import Planner
from app.models.schemas import (
    ActionSession,
    AssistantReply,
    ConfirmationRequest,
    ExecutionResult,
    RequestMode,
    StepStatus,
    UserRequest,
)
from app.services.local_model import LocalModelClient, LocalModelStatus
from app.services.session_store import SessionStore
from app.services.tool_registry import ToolRegistry


class AssistantService:
    def __init__(self) -> None:
        self.planner = Planner()
        self.tools = ToolRegistry()
        self.local_model = LocalModelClient()
        self.store = SessionStore(Path("data") / "sessions")

    def handle_request(self, payload: UserRequest) -> AssistantReply:
        plan = self.planner.build_plan(payload)
        session = ActionSession(request=payload, plan=plan)
        observations: list[str] = []
        model_status = self.local_model.status()
        observations.append(f"Local model: {model_status.message}")

        for step in session.plan.steps:
            result = self.tools.inspect(step)
            observations.append(f"{step.description}: {result.message}")
            if result.details:
                observations.extend(result.details[:5])

        session.observations = observations

        if not session.plan.requires_confirmation and infer_mode(payload) == RequestMode.ASK:
            execution = self._execute_plan(session, allow_writes=False)
            session.execution_result = execution

        self.store.save(session)
        return AssistantReply(
            session_id=session.id,
            mode=infer_mode(payload),
            summary=session.plan.summary,
            observations=session.observations,
            plan=session.plan,
            execution_result=session.execution_result,
        )

    def confirm_execution(self, payload: ConfirmationRequest) -> AssistantReply:
        session = self.store.get(payload.session_id)
        if not payload.approved:
            result = ExecutionResult(success=True, message="Execution canceled by user.")
            session.execution_result = result
            self.store.save(session)
            return AssistantReply(
                session_id=session.id,
                mode=infer_mode(session.request),
                summary="Execution canceled.",
                observations=session.observations,
                plan=session.plan,
                execution_result=result,
            )

        session.confirmed = True
        session.execution_result = self._execute_plan(session, allow_writes=True)
        self.store.save(session)
        return AssistantReply(
            session_id=session.id,
            mode=infer_mode(session.request),
            summary="Execution completed." if session.execution_result.success else "Execution failed.",
            observations=session.observations,
            plan=session.plan,
            execution_result=session.execution_result,
        )

    def _execute_plan(self, session: ActionSession, allow_writes: bool) -> ExecutionResult:
        details: list[str] = []
        all_success = True
        for step in session.plan.steps:
            if step.requires_confirmation and not allow_writes:
                step.status = StepStatus.BLOCKED
                details.append(f"Blocked step: {step.description}")
                continue
            result = self.tools.execute(step)
            details.append(f"{step.description}: {result.message}")
            details.extend(result.details[:5])
            step.status = StepStatus.COMPLETED if result.success else StepStatus.FAILED
            all_success = all_success and result.success

        message = "Plan executed." if all_success else "Plan finished with one or more failures."
        return ExecutionResult(success=all_success, message=message, details=details)

    def model_status(self) -> LocalModelStatus:
        return self.local_model.status()


assistant_service = AssistantService()
