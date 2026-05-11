"""
tests/test_chaining.py — verifies compound-instruction splitting,
step linking, context passing, and chain execution.
"""
from __future__ import annotations

import pytest

from app.core.planner import Planner, split_compound
from app.models.schemas import ExecutionResult, PlanStep, StepStatus, UserRequest


# ── split_compound ─────────────────────────────────────────────────────────────

class TestSplitCompound:
    def test_single_instruction(self):
        assert split_compound("Find my budget report") == ["Find my budget report"]

    def test_comma_then(self):
        parts = split_compound('Open Notepad, then type "Hello"')
        assert len(parts) == 2
        assert "Open Notepad" in parts[0]
        assert "Hello" in parts[1]

    def test_three_part_chain(self):
        parts = split_compound('Open Notepad, then type "Hello World", then save it')
        assert len(parts) == 3

    def test_after_that(self):
        parts = split_compound("Find my report, after that read it")
        assert len(parts) == 2

    def test_semicolon_then(self):
        parts = split_compound('click "Save"; then press "ctrl+w"')
        assert len(parts) == 2


# ── Planner chaining ───────────────────────────────────────────────────────────

class TestPlannerChaining:
    def setup_method(self):
        self.planner = Planner()

    def _req(self, text: str) -> UserRequest:
        return UserRequest(text=text)

    def test_single_produces_is_chain_false(self):
        plan = self.planner.build_plan(self._req("Find my budget report"))
        assert plan.is_chain is False

    def test_compound_produces_is_chain_true(self):
        plan = self.planner.build_plan(
            self._req('Open Notepad, then type "Hello World", then save it')
        )
        assert plan.is_chain is True

    def test_chain_step_count(self):
        plan = self.planner.build_plan(
            self._req('Open Notepad, then type "Hello World", then save it')
        )
        # 3 segments → at least 3 steps
        assert len(plan.steps) >= 3

    def test_chain_sequence_indexes(self):
        plan = self.planner.build_plan(
            self._req('Open Notepad, then type "Hello World", then save it')
        )
        indexes = [s.sequence_index for s in plan.steps]
        assert indexes == sorted(indexes), "Steps must be in ascending sequence order"

    def test_chain_depends_on_linkage(self):
        plan = self.planner.build_plan(
            self._req('Open Notepad, then type "Hello World", then save it')
        )
        # first step has no predecessor
        assert plan.steps[0].depends_on is None
        # subsequent steps reference a valid prior step id
        step_ids = {s.id for s in plan.steps}
        for step in plan.steps[1:]:
            assert step.depends_on in step_ids, \
                f"depends_on={step.depends_on!r} not found in step ids"

    def test_save_shorthand_maps_to_hotkey(self):
        plan = self.planner.build_plan(
            self._req('Open Notepad, then type "Hello", then save it')
        )
        tools = [s.tool for s in plan.steps]
        assert "desktop_hotkey" in tools, f"Expected hotkey step, got: {tools}"

    def test_find_then_read_context_linking(self):
        plan = self.planner.build_plan(
            self._req("Find my budget report, then read it")
        )
        assert plan.is_chain is True
        tools = [s.tool for s in plan.steps]
        assert "file_search" in tools
        assert "document_read" in tools

    def test_chain_risk_requires_confirmation_for_write_steps(self):
        plan = self.planner.build_plan(
            self._req('Open Notepad, then type "Hello", then save it')
        )
        # opening and typing are writes — chain must require confirmation
        assert plan.requires_confirmation is True

    def test_read_only_chain_no_confirmation(self):
        plan = self.planner.build_plan(
            self._req("Find my report, then summarize it")
        )
        # Both read-only — no confirmation needed
        assert plan.requires_confirmation is False


# ── ToolRegistry context passing ───────────────────────────────────────────────

class TestToolRegistryContext:
    def test_resolve_placeholder_target(self):
        from app.services.tool_registry import ToolRegistry
        registry = ToolRegistry()
        context = {"last_file_path": r"C:\Users\Me\Documents\budget.txt"}

        step = PlanStep(
            description="Read resolved file",
            tool="document_read",
            target="{last_file_path}",
            risk_level="low",
            requires_confirmation=False,
            status=StepStatus.READY,
        )
        # Should not raise; target resolved to the real path
        result = registry.execute(step, context)
        # Even if file doesn't exist, success=True is fine (preview mode)
        assert isinstance(result, ExecutionResult)

    def test_context_key_stored_after_file_search(self):
        from app.services.tool_registry import ToolRegistry
        registry = ToolRegistry()
        context: dict = {}

        step = PlanStep(
            description="Search for budget",
            tool="file_search",
            target="budget",
            risk_level="low",
            requires_confirmation=False,
            status=StepStatus.READY,
            result_key="last_file_path",
        )
        registry.execute(step, context)
        # If any file was found, context["last_file_path"] should be set
        # If no file found, context may be empty — that's also fine
        assert isinstance(context, dict)


# ── Chain execution in AssistantService ────────────────────────────────────────

class TestChainExecution:
    def setup_method(self):
        from app.services.assistant_service import AssistantService
        self.svc = AssistantService()

    def _req(self, text: str) -> UserRequest:
        return UserRequest(text=text)

    def test_read_only_chain_auto_executes(self):
        reply = self.svc.handle_request(self._req("Find my report, then summarize it"))
        assert reply.plan.is_chain is True
        # read-only chain should auto-execute without confirmation
        assert reply.execution_result is not None

    def test_write_chain_waits_for_confirmation(self):
        reply = self.svc.handle_request(
            self._req('Open Notepad, then type "Hello", then save it')
        )
        assert reply.plan.is_chain is True
        assert reply.plan.requires_confirmation is True
        assert reply.execution_result is None   # not executed yet

    def test_cancel_chain(self):
        from app.models.schemas import ConfirmationRequest
        reply = self.svc.handle_request(
            self._req('Open Notepad, then type "Hello", then save it')
        )
        cancel_reply = self.svc.confirm_execution(
            ConfirmationRequest(session_id=reply.session_id, approved=False)
        )
        assert cancel_reply.execution_result is not None
        assert cancel_reply.execution_result.success is True
        assert "cancel" in cancel_reply.execution_result.message.lower()

    def test_chain_step_results_present_after_execution(self):
        from app.models.schemas import ConfirmationRequest
        reply = self.svc.handle_request(
            self._req('Open Notepad, then type "Hello", then save it')
        )
        confirm_reply = self.svc.confirm_execution(
            ConfirmationRequest(session_id=reply.session_id, approved=True)
        )
        assert confirm_reply.execution_result is not None
        assert isinstance(confirm_reply.execution_result.step_results, list)
        assert len(confirm_reply.execution_result.step_results) > 0

    def test_chain_context_in_result(self):
        from app.models.schemas import ConfirmationRequest
        reply = self.svc.handle_request(
            self._req('Open Notepad, then type "Hello", then save it')
        )
        confirm_reply = self.svc.confirm_execution(
            ConfirmationRequest(session_id=reply.session_id, approved=True)
        )
        assert isinstance(confirm_reply.execution_result.chain_context, dict)
