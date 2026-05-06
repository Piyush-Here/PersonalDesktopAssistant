from __future__ import annotations

import os
from pathlib import Path

from app.models.schemas import ExecutionResult, PlanStep


class DesktopActionsTool:
    def preview(self, step: PlanStep) -> ExecutionResult:
        return ExecutionResult(
            success=True,
            message=f"{step.tool} is ready but requires confirmation.",
            details=[step.preview or f"Target: {step.target}"],
        )

    def execute(self, step: PlanStep) -> ExecutionResult:
        try:
            if step.tool == "app_open":
                target = Path(step.target).expanduser()
                if target.exists():
                    os.startfile(str(target))
                    return ExecutionResult(success=True, message=f"Opened {target}.")
                return ExecutionResult(
                    success=False,
                    message=f"Target not found: {step.target}",
                    details=["Use a full path or search for the file first."],
                )

            if step.tool == "file_copy":
                return ExecutionResult(
                    success=False,
                    message="File copy execution needs explicit source and destination paths.",
                    details=["V1 planner does not yet extract both endpoints automatically."],
                )
            if step.tool == "file_move":
                return ExecutionResult(
                    success=False,
                    message="File move execution needs explicit source and destination paths.",
                    details=["V1 planner does not yet extract both endpoints automatically."],
                )
            if step.tool == "file_rename":
                return ExecutionResult(
                    success=False,
                    message="File rename execution needs explicit old and new names.",
                    details=["V1 planner does not yet extract rename arguments automatically."],
                )
            if step.tool == "file_delete":
                return ExecutionResult(
                    success=False,
                    message="File delete is intentionally blocked in V1.",
                    details=["Keep delete behind a stricter review path before enabling it."],
                )
            if step.tool == "file_write":
                return ExecutionResult(success=False, message="Generic file write is not implemented in V1.")
        except Exception as exc:
            return ExecutionResult(success=False, message=f"Execution failed: {exc}")

        return ExecutionResult(success=False, message=f"Unsupported action {step.tool}.")
