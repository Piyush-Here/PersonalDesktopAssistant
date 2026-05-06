from unittest.mock import Mock, patch

from app.core.planner import Planner
from app.models.schemas import RequestMode, UserRequest
from app.tools.desktop_actions import DesktopActionsTool, UiTarget


def test_click_request_extracts_coordinates_and_requires_confirmation() -> None:
    plan = Planner().build_plan(UserRequest(text="click x=420 y=260", mode=RequestMode.ACT))

    step = plan.steps[0]
    assert step.tool == "desktop_click"
    assert step.metadata == {"x": 420, "y": 260}
    assert step.requires_confirmation is True
    assert step.risk_score >= 75


def test_click_target_request_extracts_visible_text_and_requires_confirmation() -> None:
    plan = Planner().build_plan(UserRequest(text='click "Save"', mode=RequestMode.ACT))

    step = plan.steps[0]
    assert step.tool == "desktop_click_target"
    assert step.metadata == {"target_text": "Save"}
    assert step.requires_confirmation is True
    assert step.risk_score >= 75


def test_type_request_extracts_quoted_text() -> None:
    plan = Planner().build_plan(UserRequest(text='type "hello world"', mode=RequestMode.ACT))

    step = plan.steps[0]
    assert step.tool == "desktop_type"
    assert step.metadata == {"text": "hello world"}
    assert step.requires_confirmation is True


def test_type_target_request_extracts_text_and_visible_target() -> None:
    plan = Planner().build_plan(UserRequest(text='type "Piyush" into "Name"', mode=RequestMode.ACT))

    step = plan.steps[0]
    assert step.tool == "desktop_type_target"
    assert step.metadata == {"text": "Piyush", "target_text": "Name"}
    assert step.requires_confirmation is True
    assert step.risk_score >= 75


def test_hotkey_request_extracts_keys() -> None:
    plan = Planner().build_plan(UserRequest(text='press "ctrl+s"', mode=RequestMode.ACT))

    step = plan.steps[0]
    assert step.tool == "desktop_hotkey"
    assert step.metadata == {"keys": ["ctrl", "s"]}
    assert step.requires_confirmation is True


def test_desktop_click_uses_pyautogui_adapter() -> None:
    plan = Planner().build_plan(UserRequest(text="click x=420 y=260", mode=RequestMode.ACT))
    pyautogui = Mock()

    with patch.object(DesktopActionsTool, "_load_pyautogui", return_value=pyautogui):
        result = DesktopActionsTool().execute(plan.steps[0])

    assert result.success is True
    pyautogui.click.assert_called_once_with(x=420, y=260)


def test_click_target_preview_resolves_center_point() -> None:
    plan = Planner().build_plan(UserRequest(text='click "Save"', mode=RequestMode.ACT))
    target = UiTarget(
        label="Save",
        control_type="Button",
        bounds=(10, 20, 110, 60),
        center=(60, 40),
    )

    with patch.object(DesktopActionsTool, "_resolve_visible_target", return_value=target):
        result = DesktopActionsTool().preview(plan.steps[0])

    assert result.success is True
    assert "resolved" in result.message
    assert plan.steps[0].metadata["x"] == 60
    assert plan.steps[0].metadata["y"] == 40
    assert plan.steps[0].metadata["resolved_label"] == "Save"


def test_click_target_execution_clicks_resolved_point() -> None:
    plan = Planner().build_plan(UserRequest(text='click "Save"', mode=RequestMode.ACT))
    target = UiTarget(
        label="Save",
        control_type="Button",
        bounds=(10, 20, 110, 60),
        center=(60, 40),
    )
    pyautogui = Mock()

    with (
        patch.object(DesktopActionsTool, "_resolve_visible_target", return_value=target),
        patch.object(DesktopActionsTool, "_load_pyautogui", return_value=pyautogui),
    ):
        result = DesktopActionsTool().execute(plan.steps[0])

    assert result.success is True
    pyautogui.click.assert_called_once_with(x=60, y=40)


def test_click_target_execution_refuses_unresolved_target() -> None:
    plan = Planner().build_plan(UserRequest(text='click "Save"', mode=RequestMode.ACT))
    pyautogui = Mock()

    with (
        patch.object(DesktopActionsTool, "_resolve_visible_target", return_value=None),
        patch.object(DesktopActionsTool, "_load_pyautogui", return_value=pyautogui),
    ):
        result = DesktopActionsTool().execute(plan.steps[0])

    assert result.success is False
    assert "No visible UI target resolved" in result.message
    pyautogui.click.assert_not_called()


def test_desktop_type_uses_pyautogui_adapter() -> None:
    plan = Planner().build_plan(UserRequest(text='type "hello"', mode=RequestMode.ACT))
    pyautogui = Mock()

    with patch.object(DesktopActionsTool, "_load_pyautogui", return_value=pyautogui):
        result = DesktopActionsTool().execute(plan.steps[0])

    assert result.success is True
    pyautogui.write.assert_called_once_with("hello", interval=0.01)


def test_type_target_preview_resolves_focus_point() -> None:
    plan = Planner().build_plan(UserRequest(text='type "Piyush" into "Name"', mode=RequestMode.ACT))
    target = UiTarget(
        label="Name",
        control_type="Edit",
        bounds=(20, 30, 220, 70),
        center=(120, 50),
    )

    with patch.object(DesktopActionsTool, "_resolve_visible_target", return_value=target):
        result = DesktopActionsTool().preview(plan.steps[0])

    assert result.success is True
    assert "resolved" in result.message
    assert plan.steps[0].metadata["x"] == 120
    assert plan.steps[0].metadata["y"] == 50
    assert plan.steps[0].metadata["resolved_control_type"] == "Edit"


def test_type_target_execution_clicks_then_types() -> None:
    plan = Planner().build_plan(UserRequest(text='type "Piyush" into "Name"', mode=RequestMode.ACT))
    target = UiTarget(
        label="Name",
        control_type="Edit",
        bounds=(20, 30, 220, 70),
        center=(120, 50),
    )
    pyautogui = Mock()

    with (
        patch.object(DesktopActionsTool, "_resolve_visible_target", return_value=target),
        patch.object(DesktopActionsTool, "_load_pyautogui", return_value=pyautogui),
    ):
        result = DesktopActionsTool().execute(plan.steps[0])

    assert result.success is True
    pyautogui.click.assert_called_once_with(x=120, y=50)
    pyautogui.write.assert_called_once_with("Piyush", interval=0.01)


def test_type_target_execution_refuses_unresolved_target() -> None:
    plan = Planner().build_plan(UserRequest(text='type "Piyush" into "Name"', mode=RequestMode.ACT))
    pyautogui = Mock()

    with (
        patch.object(DesktopActionsTool, "_resolve_visible_target", return_value=None),
        patch.object(DesktopActionsTool, "_load_pyautogui", return_value=pyautogui),
    ):
        result = DesktopActionsTool().execute(plan.steps[0])

    assert result.success is False
    assert "No visible UI target resolved" in result.message
    pyautogui.click.assert_not_called()
    pyautogui.write.assert_not_called()


def test_desktop_hotkey_uses_pyautogui_adapter() -> None:
    plan = Planner().build_plan(UserRequest(text='press "ctrl+s"', mode=RequestMode.ACT))
    pyautogui = Mock()

    with patch.object(DesktopActionsTool, "_load_pyautogui", return_value=pyautogui):
        result = DesktopActionsTool().execute(plan.steps[0])

    assert result.success is True
    pyautogui.hotkey.assert_called_once_with("ctrl", "s")
