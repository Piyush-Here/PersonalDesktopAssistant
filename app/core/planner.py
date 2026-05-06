from __future__ import annotations

from pathlib import Path

from app.core.intent import extract_quoted_text, infer_mode
from app.core.safety import classify_risk, requires_confirmation
from app.models.schemas import Plan, PlanStep, RequestMode, StepStatus, UserRequest


class Planner:
    def build_plan(self, request: UserRequest) -> Plan:
        mode = infer_mode(request)
        text = request.text.strip()
        text_lower = text.lower()
        steps: list[PlanStep] = []

        if any(word in text_lower for word in ("find", "search", "latest", "newest")):
            target = self._extract_target(text)
            steps.append(
                self._make_step(
                    description=f"Search local files for {target}",
                    tool="file_search",
                    target=target,
                    preview="Will inspect indexed folders and return matching files.",
                )
            )

        if any(word in text_lower for word in ("read", "summarize", "explain")):
            target = self._extract_target(text)
            steps.append(
                self._make_step(
                    description=f"Read accessible content for {target}",
                    tool="document_read",
                    target=target,
                    preview="Will parse supported document types and summarize their content.",
                )
            )

        if "open" in text_lower or "launch" in text_lower:
            target = self._extract_target(text)
            steps.append(
                self._make_step(
                    description=f"Open application or file {target}",
                    tool="app_open",
                    target=target,
                    preview="Will resolve the file or app path, then wait for confirmation before opening.",
                )
            )

        if any(word in text_lower for word in ("rename", "move", "copy", "delete")):
            target = self._extract_target(text)
            tool = self._detect_file_action(text_lower)
            steps.append(
                self._make_step(
                    description=f"Prepare {tool.replace('_', ' ')} operation for {target}",
                    tool=tool,
                    target=target,
                    preview="Will gather targets and show the exact change before execution.",
                )
            )

        if "screen" in text_lower or "on screen" in text_lower:
            steps.append(
                self._make_step(
                    description="Inspect active screen content",
                    tool="screen_inspect",
                    target="active screen",
                    preview="Will capture current window metadata and screen text when available.",
                )
            )

        if not steps:
            fallback_tool = "assistant_answer" if mode == RequestMode.ASK else "screen_inspect"
            steps.append(
                self._make_step(
                    description="Interpret request and gather local context",
                    tool=fallback_tool,
                    target="general request",
                    preview="Will gather context conservatively and return a safe next action.",
                )
            )

        confirmation_required = any(step.requires_confirmation for step in steps)
        summary = self._build_summary(steps, mode)
        return Plan(summary=summary, steps=steps, requires_confirmation=confirmation_required)

    def _extract_target(self, text: str) -> str:
        quoted = extract_quoted_text(text)
        if quoted:
            return quoted[0]
        words = text.split()
        if len(words) <= 4:
            return text
        return " ".join(words[1:6])

    def _detect_file_action(self, text_lower: str) -> str:
        mapping = {
            "rename": "file_rename",
            "move": "file_move",
            "copy": "file_copy",
            "delete": "file_delete",
        }
        for keyword, tool in mapping.items():
            if keyword in text_lower:
                return tool
        return "file_write"

    def _make_step(self, description: str, tool: str, target: str, preview: str) -> PlanStep:
        step = PlanStep(
            description=description,
            tool=tool,
            target=target or str(Path.home()),
            risk_level="low",
            requires_confirmation=False,
            status=StepStatus.READY,
            preview=preview,
        )
        step.risk_level = classify_risk(step)
        step.requires_confirmation = requires_confirmation(step)
        return step

    def _build_summary(self, steps: list[PlanStep], mode: RequestMode) -> str:
        if mode == RequestMode.ASK:
            return f"I interpreted this as a read-only request and prepared {len(steps)} step(s)."
        if any(step.requires_confirmation for step in steps):
            return f"I prepared {len(steps)} step(s) and paused before any state-changing action."
        return f"I prepared {len(steps)} step(s) for immediate execution."
