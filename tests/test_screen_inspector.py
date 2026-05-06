from app.tools.screen_inspector import ActiveWindowInfo, ScreenInspectorTool


def test_screen_inspector_reports_active_window_metadata(monkeypatch) -> None:
    tool = ScreenInspectorTool()
    monkeypatch.setattr(
        tool,
        "_active_window_info",
        lambda: ActiveWindowInfo(
            title="Notes",
            handle=123,
            process_id=456,
            bounds=(1, 2, 300, 400),
        ),
    )
    monkeypatch.setattr(tool, "_screenshot_details", lambda: ["Screenshot capture available: 1920x1080."])
    monkeypatch.setattr(tool, "_ui_automation_details", lambda hwnd: [f"UIA handle: {hwnd}"])
    monkeypatch.setattr(tool, "_ocr_details", lambda: ["OCR text preview: hello"])

    result = tool.preview("active screen")

    assert result.success is True
    assert "Screen inspection completed" in result.message
    assert "Active window: Notes" in result.details
    assert "Window handle: 123" in result.details
    assert "UIA handle: 123" in result.details
    assert "OCR text preview: hello" in result.details


def test_screen_inspector_handles_missing_window(monkeypatch) -> None:
    tool = ScreenInspectorTool()
    monkeypatch.setattr(tool, "_active_window_info", lambda: None)
    monkeypatch.setattr(tool, "_screenshot_details", lambda: ["Screenshot capture unavailable."])
    monkeypatch.setattr(tool, "_ui_automation_details", lambda hwnd: [f"UIA skipped: {hwnd}"])
    monkeypatch.setattr(tool, "_ocr_details", lambda: ["OCR unavailable."])

    result = tool.preview("active screen")

    assert result.success is True
    assert "Active window metadata is not available on this platform or permission context." in result.details
    assert "UIA skipped: None" in result.details
