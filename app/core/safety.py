from __future__ import annotations

from app.models.schemas import PlanStep, RiskAssessment, RiskLevel


HIGH_RISK_TOOLS = {
    "file_delete",
    "desktop_command",
    "desktop_click",
    "desktop_click_target",
    "desktop_type",
    "desktop_type_target",
    "desktop_hotkey",
    "message_send",
    "settings_change",
}
WRITE_TOOLS = {
    "file_write",
    "file_move",
    "file_copy",
    "file_rename",
    "app_open",
    "desktop_command",
    "desktop_click",
    "desktop_click_target",
    "desktop_type",
    "desktop_type_target",
    "desktop_hotkey",
}


def classify_risk(step: PlanStep) -> RiskLevel:
    return assess_step_risk(step).level


def requires_confirmation(step: PlanStep) -> bool:
    return step.tool in HIGH_RISK_TOOLS or step.tool in WRITE_TOOLS


def assess_step_risk(step: PlanStep) -> RiskAssessment:
    score = 10
    reasons = ["Read-only local inspection."] if step.tool not in WRITE_TOOLS else []

    if step.tool in WRITE_TOOLS:
        score = 55
        reasons.append("Changes local desktop or file state.")

    if step.tool in HIGH_RISK_TOOLS:
        score = 90
        reasons.append("High impact action is blocked or requires stricter review.")

    if step.tool == "app_open":
        score = max(score, 45)
        reasons.append("Launches a local app or file.")

    if step.tool in {"file_copy", "file_move", "file_rename"}:
        if step.metadata.get("source_path") and step.metadata.get("destination_path"):
            score = max(score, 50)
            reasons.append("Uses explicit source and destination paths.")
        else:
            score = max(score, 70)
            reasons.append("Missing exact file-operation endpoints.")

    if step.tool == "file_delete":
        score = 95
        reasons.append("Deletes data and remains disabled.")

    if step.tool in {"desktop_click", "desktop_click_target", "desktop_type", "desktop_type_target", "desktop_hotkey"}:
        score = max(score, 82)
        reasons.append("Controls the active desktop session.")
        if step.tool == "desktop_click" and not {"x", "y"}.issubset(step.metadata):
            score = max(score, 92)
            reasons.append("Missing explicit click coordinates.")
        if step.tool == "desktop_click_target":
            reasons.append("Resolves a visible UI target before clicking.")
            if not step.metadata.get("target_text"):
                score = max(score, 92)
                reasons.append("Missing explicit visible target text.")
        if step.tool == "desktop_type" and not step.metadata.get("text"):
            score = max(score, 92)
            reasons.append("Missing explicit text to type.")
        if step.tool == "desktop_type_target":
            reasons.append("Resolves a visible UI target before typing.")
            if not step.metadata.get("target_text"):
                score = max(score, 92)
                reasons.append("Missing explicit visible target text.")
            if not step.metadata.get("text"):
                score = max(score, 92)
                reasons.append("Missing explicit text to type.")
        if step.tool == "desktop_hotkey" and not step.metadata.get("keys"):
            score = max(score, 92)
            reasons.append("Missing explicit key or hotkey.")

    level = _level_for_score(score)
    return RiskAssessment(
        score=score,
        level=level,
        requires_confirmation=requires_confirmation(step),
        reasons=reasons,
    )


def assess_plan_risk(steps: list[PlanStep]) -> RiskAssessment:
    if not steps:
        return RiskAssessment(
            score=0,
            level=RiskLevel.LOW,
            requires_confirmation=False,
            reasons=["No executable steps were planned."],
        )

    step_risks = [assess_step_risk(step) for step in steps]
    score = max(risk.score for risk in step_risks)
    requires_approval = any(risk.requires_confirmation for risk in step_risks)
    reasons: list[str] = []

    if len(steps) > 1:
        score = min(100, score + 5)
        reasons.append(f"Chain contains {len(steps)} planned step(s).")

    for risk in step_risks:
        for reason in risk.reasons:
            if reason not in reasons:
                reasons.append(reason)

    return RiskAssessment(
        score=score,
        level=_level_for_score(score),
        requires_confirmation=requires_approval,
        reasons=reasons,
    )


def _level_for_score(score: int) -> RiskLevel:
    if score >= 75:
        return RiskLevel.HIGH
    if score >= 40:
        return RiskLevel.MEDIUM
    return RiskLevel.LOW
