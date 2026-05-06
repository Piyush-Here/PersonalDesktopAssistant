from app.core.planner import Planner
from app.models.schemas import RequestMode, UserRequest


def test_read_only_request_stays_safe() -> None:
    planner = Planner()
    plan = planner.build_plan(UserRequest(text="Find my latest report and summarize it", mode=RequestMode.ACT))
    assert plan.steps
    assert any(step.tool == "file_search" for step in plan.steps)
    assert any(step.tool == "document_read" for step in plan.steps)


def test_open_request_requires_confirmation() -> None:
    planner = Planner()
    plan = planner.build_plan(UserRequest(text="Open C:\\temp\\notes.txt", mode=RequestMode.ACT))
    assert plan.requires_confirmation is True
