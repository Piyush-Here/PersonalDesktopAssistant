from __future__ import annotations

from app.models.schemas import ExecutionResult, PlanStep
from app.tools.desktop_actions import DesktopActionsTool
from app.tools.document_reader import DocumentReaderTool
from app.tools.file_search import FileSearchTool
from app.tools.screen_inspector import ScreenInspectorTool
from app.tools.screenshot_tool import ScreenshotTool


DESKTOP_ACTION_TOOLS = {
    "app_open", "file_rename", "file_move", "file_copy", "file_delete",
    "file_write", "desktop_click", "desktop_click_target",
    "desktop_type", "desktop_type_target", "desktop_hotkey",
}


class ToolRegistry:
    def __init__(self) -> None:
        self.file_search     = FileSearchTool()
        self.document_reader = DocumentReaderTool()
        self.screen_inspector = ScreenInspectorTool()
        self.desktop_actions = DesktopActionsTool()
        self.screenshot      = ScreenshotTool()

    def inspect(self, step: PlanStep) -> ExecutionResult:
        if step.tool == "file_search":
            return self.file_search.preview(step.target)
        if step.tool == "document_read":
            return self.document_reader.preview(step.target)
        if step.tool == "screen_inspect":
            result = self.screen_inspector.preview(step.target)
            shot = self.screenshot.capture()
            if shot.success:
                return ExecutionResult(
                    success=result.success, message=result.message,
                    details=result.details + ["── Screenshot ──"] + shot.details,
                )
            return result
        if step.tool == "assistant_answer":
            return ExecutionResult(success=True, message="No direct tool matched.", details=[])
        if step.tool in DESKTOP_ACTION_TOOLS:
            return self.desktop_actions.preview(step)
        return ExecutionResult(success=False, message=f"No preview for '{step.tool}'.")

    def execute(self, step: PlanStep, context: dict | None = None) -> ExecutionResult:
        ctx = context if context is not None else {}

        # Resolve {placeholder} targets from chain context
        resolved_target = self._resolve(step.target, ctx)
        if resolved_target != step.target:
            step = step.model_copy(update={"target": resolved_target})

        resolved_meta = {
            k: self._resolve(str(v), ctx) if isinstance(v, str) else v
            for k, v in step.metadata.items()
        }
        if resolved_meta != step.metadata:
            step = step.model_copy(update={"metadata": resolved_meta})

        result = self._dispatch(step)

        # Store primary output for downstream steps
        if step.result_key and result.success and result.details:
            ctx[step.result_key] = result.details[0]

        return result

    def _dispatch(self, step: PlanStep) -> ExecutionResult:
        if step.tool in DESKTOP_ACTION_TOOLS:
            return self.desktop_actions.execute(step)
        if step.tool == "file_search":
            return self.file_search.preview(step.target)
        if step.tool == "document_read":
            return self.document_reader.preview(step.target)
        if step.tool == "screen_inspect":
            return self.screen_inspector.preview(step.target)
        if step.tool == "assistant_answer":
            return ExecutionResult(success=True, message="No specific tool matched.", details=[])
        return ExecutionResult(success=False, message=f"No handler for '{step.tool}'.")

    @staticmethod
    def _resolve(value: str, context: dict) -> str:
        for k, v in context.items():
            value = value.replace(f"{{{k}}}", str(v))
        return value
