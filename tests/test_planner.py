from pathlib import Path
from unittest.mock import patch

from app.core.planner import Planner
from app.models.schemas import RequestMode, UserRequest
from app.tools.desktop_actions import DesktopActionsTool


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
    assert plan.risk_assessment.score >= 40
    assert plan.risk_assessment.requires_confirmation is True


def test_copy_request_extracts_source_and_destination() -> None:
    planner = Planner()
    plan = planner.build_plan(
        UserRequest(
            text='Copy "C:\\temp\\source.txt" to "C:\\temp\\backup.txt"',
            mode=RequestMode.ACT,
        )
    )

    step = plan.steps[0]
    assert step.tool == "file_copy"
    assert step.requires_confirmation is True
    assert step.risk_score >= 40
    assert step.metadata["source_path"] == "C:\\temp\\source.txt"
    assert step.metadata["destination_path"] == "C:\\temp\\backup.txt"


def test_rename_request_resolves_new_name_in_same_folder() -> None:
    planner = Planner()
    plan = planner.build_plan(
        UserRequest(
            text='Rename "C:\\temp\\source.txt" to "renamed.txt"',
            mode=RequestMode.ACT,
        )
    )

    step = plan.steps[0]
    assert step.tool == "file_rename"
    assert step.metadata["source_path"] == "C:\\temp\\source.txt"
    assert step.metadata["destination_path"].endswith("C:\\temp\\renamed.txt")


def test_file_copy_executes_after_confirmation() -> None:
    planner = Planner()
    plan = planner.build_plan(
        UserRequest(
            text='Copy "C:\\temp\\source.txt" to "C:\\temp\\destination.txt"',
            mode=RequestMode.ACT,
        )
    )

    destination = Path("C:\\temp\\destination.txt")

    with (
        patch.object(DesktopActionsTool, "_validate_source_destination", return_value=None),
        patch("app.tools.desktop_actions.shutil.copy2") as copy2,
    ):
        result = DesktopActionsTool().execute(plan.steps[0])

    assert result.success is True
    copy2.assert_called_once_with(Path("C:\\temp\\source.txt"), destination)


def test_file_copy_refuses_overwrite() -> None:
    planner = Planner()
    plan = planner.build_plan(
        UserRequest(
            text='Copy "C:\\temp\\source.txt" to "C:\\temp\\destination.txt"',
            mode=RequestMode.ACT,
        )
    )

    with (
        patch.object(Path, "exists", side_effect=[True, True]),
        patch.object(Path, "is_file", return_value=True),
        patch("app.tools.desktop_actions.shutil.copy2") as copy2,
    ):
        result = DesktopActionsTool().execute(plan.steps[0])

    assert result.success is False
    assert "already exists" in result.message
    copy2.assert_not_called()
