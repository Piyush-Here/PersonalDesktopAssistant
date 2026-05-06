from __future__ import annotations

from app.models.schemas import PlanStep, RiskLevel


HIGH_RISK_TOOLS = {"file_delete", "desktop_command", "message_send", "settings_change"}
WRITE_TOOLS = {
    "file_write",
    "file_move",
    "file_copy",
    "file_rename",
    "app_open",
    "desktop_command",
}


def classify_risk(step: PlanStep) -> RiskLevel:
    if step.tool in HIGH_RISK_TOOLS:
        return RiskLevel.HIGH
    if step.tool in WRITE_TOOLS:
        return RiskLevel.MEDIUM
    return RiskLevel.LOW


def requires_confirmation(step: PlanStep) -> bool:
    return step.tool in HIGH_RISK_TOOLS or step.tool in WRITE_TOOLS
