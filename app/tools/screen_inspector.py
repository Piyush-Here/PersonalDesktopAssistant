from __future__ import annotations

import platform

from app.models.schemas import ExecutionResult


class ScreenInspectorTool:
    def preview(self, target: str) -> ExecutionResult:
        return ExecutionResult(
            success=True,
            message="Screen inspection scaffold is available.",
            details=[
                f"Platform detected: {platform.system()}",
                "V1 exposes a placeholder for active window metadata, OCR, and UI Automation hooks.",
            ],
        )
