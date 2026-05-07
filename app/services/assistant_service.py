"""
AssistantService — orchestrates planning, observation, and execution.

Phase 7 changes:
  - Uses LLMPlanner (Ollama-backed) when a local model is configured,
    falls back to deterministic Planner automatically.
  - Injects a ScreenshotTool for richer screen observations when a
    vision model is configured.
  - Exposes llm_status() for the new /api/llm/status endpoint.
"""
from __future__ import annotations

from pathlib import Path

from app.core.intent import infer_mode
from app.core.llm_planner import LLMPlanner
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
from app.tools.screenshot_tool import ScreenshotTool


class AssistantService:
    def __init__(self) -> None:
        self.planner = LLMPlanner()          # wraps deterministic planner as fallback
        self.tools = ToolRegistry()
        self.local_model = LocalModelClient()
        self.screenshot = ScreenshotTool()
        self.store = SessionStore(Path("data") / "sessions")

    # ── Request handling ───────────────────────────────────────────────────────

    def handle_request(self, payload: UserRequest) -> AssistantReply:
        plan = self.planner.build_plan(payload)
        session = ActionSession(request=payload, plan=plan)
        observations: list[str] = []

        # ── Model status note ──
        model_status = self.local_model.status()
        planner_mode = "LLM (Ollama)" if self.planner.using_llm else "deterministic"
        observations.append(f"Planner: {planner_mode} | Model status: {model_status.message}")

        # ── Tool-level inspection (pre-execution preview) ──
        for step in session.plan.steps:
            result = self.tools.inspect(step)
            observations.append(f"{step.description}: {result.message}")
            if result.details:
                observations.extend(result.details[:5])

        # ── Optional: capture screen for context when screen_inspect is in plan ──
        if any(s.tool == "screen_inspect" for s in session.plan.steps):
            shot_result = self.screenshot.capture()
            if shot_result.success:
                observations.extend(shot_result.details[:6])

        session.observations = observations

        # ── Auto-execute read-only ASK plans ──
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

    def model_status(self) -> LocalModelStatus:
        return self.local_model.status()

    def llm_status(self) -> dict[str, object]:
        """Return a dict describing the current planner configuration."""
        model_status = self.local_model.status()
        return {
            "planner": "ollama" if self.planner.using_llm else "deterministic",
            "llm_active": self.planner.using_llm,
            "model": self.planner.model if self.planner.using_llm else None,
            "endpoint": self.planner.endpoint if self.planner.using_llm else None,
            "model_available": model_status.available,
            "message": model_status.message,
        }

    # ── Internal execution ─────────────────────────────────────────────────────

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


assistant_service = AssistantService()
