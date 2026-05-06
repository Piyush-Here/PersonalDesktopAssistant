from __future__ import annotations

from app.models.schemas import ExecutionResult, PlanStep
from app.tools.desktop_actions import DesktopActionsTool
from app.tools.document_reader import DocumentReaderTool
from app.tools.file_search import FileSearchTool
from app.tools.screen_inspector import ScreenInspectorTool


class ToolRegistry:
    def __init__(self) -> None:
        self.file_search = FileSearchTool()
        self.document_reader = DocumentReaderTool()
        self.screen_inspector = ScreenInspectorTool()
        self.desktop_actions = DesktopActionsTool()

    def inspect(self, step: PlanStep) -> ExecutionResult:
        if step.tool == "file_search":
            return self.file_search.preview(step.target)
        if step.tool == "document_read":
            return self.document_reader.preview(step.target)
        if step.tool == "screen_inspect":
            return self.screen_inspector.preview(step.target)
        if step.tool == "assistant_answer":
            return ExecutionResult(
                success=True,
                message="No direct tool matched. The assistant recommends narrowing the request.",
                details=["Try specifying a file, app, or screen target."],
            )
        if step.tool in {"app_open", "file_rename", "file_move", "file_copy", "file_delete", "file_write"}:
            return self.desktop_actions.preview(step)
        return ExecutionResult(success=False, message=f"No preview tool available for {step.tool}.")

    def execute(self, step: PlanStep) -> ExecutionResult:
        if step.tool in {"app_open", "file_rename", "file_move", "file_copy", "file_delete", "file_write"}:
            return self.desktop_actions.execute(step)
        if step.tool == "file_search":
            return self.file_search.preview(step.target)
        if step.tool == "document_read":
            return self.document_reader.preview(step.target)
        if step.tool == "screen_inspect":
            return self.screen_inspector.preview(step.target)
        return ExecutionResult(success=False, message=f"No execution tool available for {step.tool}.")
