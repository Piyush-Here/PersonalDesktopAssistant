"""
AssistantService — orchestrates planning, observation, and chain execution.

Chain execution:
- Runs steps in sequence_index order
- Each step receives the shared context dict so it can consume
  outputs from prior steps (e.g. {last_file_path})
- Aborts the chain on first failure (abort_on_failure=True by default)
- Reports per-step results in ExecutionResult.step_results
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
        self.planner      = LLMPlanner()
        self.tools        = ToolRegistry()
        self.local_model  = LocalModelClient()
        self.screenshot   = ScreenshotTool()
        self.store        = SessionStore(Path("data") / "sessions")

    # ── Request handling ──────────────────────────────────────────────────────

    def handle_request(self, payload: UserRequest) -> AssistantReply:
        plan    = self.planner.build_plan(payload)
        session = ActionSession(request=payload, plan=plan)

        observations: list[str] = []
        model_status = self.local_model.status()
        planner_mode = "LLM (Ollama)" if self.planner.using_llm else "deterministic"
        observations.append(
            f"Planner: {planner_mode} | Chain: {'yes' if plan.is_chain else 'no'} "
            f"({len(plan.steps)} step{'s' if len(plan.steps)!=1 else ''}) | "
            f"Model: {model_status.message}"
        )

        for step in session.plan.steps:
            result = self.tools.inspect(step)
            observations.append(f"[{step.sequence_index+1}] {step.description}: {result.message}")
            if result.details:
                observations.extend(result.details[:3])

        if any(s.tool == "screen_inspect" for s in session.plan.steps):
            shot = self.screenshot.capture()
            if shot.success:
                observations.extend(shot.details[:4])

        session.observations = observations

        # Auto-execute if read-only (no confirmation steps)
        if not session.plan.requires_confirmation and infer_mode(payload) == RequestMode.ASK:
            session.execution_result = self._execute_chain(session, allow_writes=False)

        self.store.save(session)
        return self._make_reply(session, payload)

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
        session.execution_result = self._execute_chain(session, allow_writes=True)
        self.store.save(session)
        return AssistantReply(
            session_id=session.id,
            mode=infer_mode(session.request),
            summary=(
                "Chain completed successfully." if session.execution_result.success
                else "Chain finished with one or more failures."
            ),
            observations=session.observations,
            plan=session.plan,
            execution_result=session.execution_result,
        )

    def model_status(self) -> LocalModelStatus:
        return self.local_model.status()

    def llm_status(self) -> dict[str, object]:
        ms = self.local_model.status()
        return {
            "planner": "ollama" if self.planner.using_llm else "deterministic",
            "llm_active": self.planner.using_llm,
            "model": self.planner.model if self.planner.using_llm else None,
            "endpoint": self.planner.endpoint if self.planner.using_llm else None,
            "model_available": ms.available,
            "message": ms.message,
        }

    # ── Chain execution engine ────────────────────────────────────────────────

    def _execute_chain(
        self,
        session: ActionSession,
        allow_writes: bool,
        abort_on_failure: bool = True,
    ) -> ExecutionResult:
        """
        Execute all steps in sequence_index order.

        - Shared `context` dict flows through every step so outputs
          (e.g. last_file_path) are available to later steps.
        - If abort_on_failure is True, stops at the first failed step
          and marks remaining steps as BLOCKED.
        """
        context: dict = {}
        step_results: list[dict] = []
        all_success = True
        aborted = False

        sorted_steps = sorted(session.plan.steps, key=lambda s: s.sequence_index)

        for step in sorted_steps:
            if aborted:
                step.status = StepStatus.BLOCKED
                step_results.append({
                    "step": step.description,
                    "status": "blocked",
                    "message": "Skipped — earlier step in chain failed.",
                })
                continue

            if step.requires_confirmation and not allow_writes:
                step.status = StepStatus.BLOCKED
                step_results.append({
                    "step": step.description,
                    "status": "blocked",
                    "message": "Blocked — requires confirmation.",
                })
                continue

            result = self.tools.execute(step, context)
            step.status = StepStatus.COMPLETED if result.success else StepStatus.FAILED

            step_results.append({
                "step": step.description,
                "status": step.status.value,
                "message": result.message,
                "details": result.details[:5],
            })

            if not result.success:
                all_success = False
                if abort_on_failure:
                    aborted = True

        # Build a human-readable summary of the chain result
        completed = sum(1 for r in step_results if r["status"] == "completed")
        total     = len(sorted_steps)

        if all_success:
            message = (
                f"All {total} step{'s' if total != 1 else ''} completed successfully."
            )
        else:
            message = (
                f"{completed}/{total} step{'s' if total != 1 else ''} completed. "
                + ("Remaining steps were skipped." if aborted else "")
            )

        # Flatten all step details into the top-level details list
        details: list[str] = []
        for r in step_results:
            status_icon = {"completed": "✓", "failed": "✗", "blocked": "—"}.get(r["status"], "?")
            details.append(f"{status_icon} [{r['status'].upper()}] {r['step']}: {r['message']}")
            details.extend(f"  {d}" for d in r.get("details", []))

        return ExecutionResult(
            success=all_success,
            message=message,
            details=details,
            step_results=step_results,
            chain_context=dict(context),
        )

    def _make_reply(self, session: ActionSession, payload: UserRequest) -> AssistantReply:
        return AssistantReply(
            session_id=session.id,
            mode=infer_mode(payload),
            summary=session.plan.summary,
            observations=session.observations,
            plan=session.plan,
            execution_result=session.execution_result,
        )


assistant_service = AssistantService()
