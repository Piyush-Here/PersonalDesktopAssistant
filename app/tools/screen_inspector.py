from __future__ import annotations

import platform
from dataclasses import dataclass

from app.models.schemas import ExecutionResult


@dataclass(frozen=True)
class ActiveWindowInfo:
    title: str
    handle: int
    process_id: int
    bounds: tuple[int, int, int, int]


class ScreenInspectorTool:
    def preview(self, target: str) -> ExecutionResult:
        details = [f"Platform detected: {platform.system()}"]
        window = self._active_window_info()
        if window is None:
            details.append("Active window metadata is not available on this platform or permission context.")
        else:
            details.extend(
                [
                    f"Active window: {window.title or '(untitled)'}",
                    f"Window handle: {window.handle}",
                    f"Process id: {window.process_id}",
                    f"Bounds: left={window.bounds[0]}, top={window.bounds[1]}, right={window.bounds[2]}, bottom={window.bounds[3]}",
                ]
            )

        details.extend(self._screenshot_details())
        details.extend(self._ui_automation_details(window.handle if window else None))
        details.extend(self._ocr_details())

        return ExecutionResult(
            success=True,
            message=f"Screen inspection completed for {target}.",
            details=details,
        )

    def _active_window_info(self) -> ActiveWindowInfo | None:
        if platform.system() != "Windows":
            return None

        try:
            import ctypes
            from ctypes import wintypes

            user32 = ctypes.windll.user32
            hwnd = user32.GetForegroundWindow()
            if not hwnd:
                return None

            length = user32.GetWindowTextLengthW(hwnd)
            buffer = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buffer, length + 1)

            process_id = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(process_id))

            rect = wintypes.RECT()
            user32.GetWindowRect(hwnd, ctypes.byref(rect))

            return ActiveWindowInfo(
                title=buffer.value,
                handle=int(hwnd),
                process_id=int(process_id.value),
                bounds=(int(rect.left), int(rect.top), int(rect.right), int(rect.bottom)),
            )
        except Exception:
            return None

    def _screenshot_details(self) -> list[str]:
        try:
            from PIL import ImageGrab

            image = ImageGrab.grab()
            width, height = image.size
            return [
                f"Screenshot capture available: {width}x{height}.",
                "Screenshot was inspected in memory and not saved.",
            ]
        except ImportError:
            return ["Screenshot capture unavailable: Pillow is not installed."]
        except Exception as exc:
            return [f"Screenshot capture unavailable: {exc}."]

    def _ui_automation_details(self, hwnd: int | None) -> list[str]:
        if hwnd is None:
            return ["UI Automation skipped: active window handle unavailable."]

        try:
            from pywinauto import Desktop

            window = Desktop(backend="uia").window(handle=hwnd)
            controls = []
            for control in window.descendants()[:12]:
                label = control.window_text()
                control_type = control.friendly_class_name()
                controls.append(f"{control_type}: {label or '(no label)'}")

            if not controls:
                return ["UI Automation available: no child controls were exposed by the active window."]
            return ["UI Automation visible controls:"] + controls
        except ImportError:
            return ["UI Automation unavailable: pywinauto is not installed."]
        except Exception as exc:
            return [f"UI Automation unavailable for active window: {exc}."]

    def _ocr_details(self) -> list[str]:
        try:
            from PIL import ImageGrab
            import pytesseract

            image = ImageGrab.grab()
            text = " ".join(pytesseract.image_to_string(image).split())
            if not text:
                return ["OCR available: no readable text detected."]
            return [f"OCR text preview: {text[:500]}"]
        except ImportError:
            return ["OCR unavailable: pytesseract is not installed."]
        except Exception as exc:
            return [f"OCR unavailable: {exc}."]
