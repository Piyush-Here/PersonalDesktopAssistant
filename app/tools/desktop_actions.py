from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from pathlib import Path

from app.models.schemas import ExecutionResult, PlanStep


@dataclass(frozen=True)
class UiTarget:
    label: str
    control_type: str
    bounds: tuple[int, int, int, int]
    center: tuple[int, int]


class DesktopActionsTool:
    def preview(self, step: PlanStep) -> ExecutionResult:
        if step.tool == "desktop_click":
            if not {"x", "y"}.issubset(step.metadata):
                return ExecutionResult(
                    success=True,
                    message="desktop_click needs explicit x and y coordinates.",
                    details=['Use a request like: click x=420 y=260.'],
                )
            return ExecutionResult(
                success=True,
                message="desktop_click is ready but requires confirmation.",
                details=[f"Coordinates: x={step.metadata['x']}, y={step.metadata['y']}"],
            )

        if step.tool == "desktop_click_target":
            target_text = step.metadata.get("target_text")
            if not target_text:
                return ExecutionResult(
                    success=True,
                    message="desktop_click_target needs explicit quoted visible text.",
                    details=['Use a request like: click "Save".'],
                )

            target = self._resolve_visible_target(str(target_text))
            if target is None:
                return ExecutionResult(
                    success=True,
                    message=f"No visible UI target resolved for '{target_text}'.",
                    details=["Inspect the screen first or use explicit coordinates."],
                )

            step.metadata.update(
                {
                    "resolved_label": target.label,
                    "resolved_control_type": target.control_type,
                    "x": target.center[0],
                    "y": target.center[1],
                    "bounds": list(target.bounds),
                }
            )
            return ExecutionResult(
                success=True,
                message="desktop_click_target resolved and requires confirmation.",
                details=[
                    f"Target: {target.control_type} '{target.label}'",
                    f"Bounds: left={target.bounds[0]}, top={target.bounds[1]}, right={target.bounds[2]}, bottom={target.bounds[3]}",
                    f"Click point: x={target.center[0]}, y={target.center[1]}",
                ],
            )

        if step.tool == "desktop_type":
            text = step.metadata.get("text")
            if not text:
                return ExecutionResult(
                    success=True,
                    message="desktop_type needs explicit quoted text.",
                    details=['Use a request like: type "hello" into the focused field.'],
                )
            return ExecutionResult(
                success=True,
                message="desktop_type is ready but requires confirmation.",
                details=[f"Text length: {len(text)} character(s)"],
            )

        if step.tool == "desktop_type_target":
            target_text = step.metadata.get("target_text")
            text = step.metadata.get("text")
            if not target_text or not text:
                return ExecutionResult(
                    success=True,
                    message="desktop_type_target needs explicit quoted text and target.",
                    details=['Use a request like: type "Piyush" into "Name".'],
                )

            target = self._resolve_visible_target(str(target_text))
            if target is None:
                return ExecutionResult(
                    success=True,
                    message=f"No visible UI target resolved for '{target_text}'.",
                    details=["Inspect the screen first or type into the currently focused control."],
                )

            step.metadata.update(
                {
                    "resolved_label": target.label,
                    "resolved_control_type": target.control_type,
                    "x": target.center[0],
                    "y": target.center[1],
                    "bounds": list(target.bounds),
                }
            )
            return ExecutionResult(
                success=True,
                message="desktop_type_target resolved and requires confirmation.",
                details=[
                    f"Target: {target.control_type} '{target.label}'",
                    f"Bounds: left={target.bounds[0]}, top={target.bounds[1]}, right={target.bounds[2]}, bottom={target.bounds[3]}",
                    f"Focus point: x={target.center[0]}, y={target.center[1]}",
                    f"Text length: {len(str(text))} character(s)",
                ],
            )

        if step.tool == "desktop_hotkey":
            keys = step.metadata.get("keys")
            if not keys:
                return ExecutionResult(
                    success=True,
                    message="desktop_hotkey needs explicit key names.",
                    details=['Use a request like: press "ctrl+s".'],
                )
            return ExecutionResult(
                success=True,
                message="desktop_hotkey is ready but requires confirmation.",
                details=[f"Keys: {' + '.join(keys)}"],
            )

        if step.tool in {"file_copy", "file_move", "file_rename"}:
            source = step.metadata.get("source_path")
            destination = step.metadata.get("destination_path")
            if not source or not destination:
                return ExecutionResult(
                    success=True,
                    message=f"{step.tool} needs explicit source and destination paths.",
                    details=['Use quoted paths, for example: copy "C:\\source.txt" to "C:\\target.txt".'],
                )
            return ExecutionResult(
                success=True,
                message=f"{step.tool} is ready but requires confirmation.",
                details=[f"Source: {source}", f"Destination: {destination}"],
            )

        return ExecutionResult(
            success=True,
            message=f"{step.tool} is ready but requires confirmation.",
            details=[step.preview or f"Target: {step.target}"],
        )

    def execute(self, step: PlanStep) -> ExecutionResult:
        try:
            if step.tool == "app_open":
                target = Path(step.target).expanduser()
                if target.exists():
                    os.startfile(str(target))
                    return ExecutionResult(success=True, message=f"Opened {target}.")
                return ExecutionResult(
                    success=False,
                    message=f"Target not found: {step.target}",
                    details=["Use a full path or search for the file first."],
                )

            if step.tool == "file_copy":
                return self._copy_file(step)
            if step.tool == "file_move":
                return self._move_file(step)
            if step.tool == "file_rename":
                return self._rename_file(step)
            if step.tool == "file_delete":
                return ExecutionResult(
                    success=False,
                    message="File delete is intentionally blocked in V1.",
                    details=["Keep delete behind a stricter review path before enabling it."],
                )
            if step.tool == "file_write":
                return ExecutionResult(success=False, message="Generic file write is not implemented in V1.")
            if step.tool == "desktop_click":
                return self._desktop_click(step)
            if step.tool == "desktop_click_target":
                return self._desktop_click_target(step)
            if step.tool == "desktop_type":
                return self._desktop_type(step)
            if step.tool == "desktop_type_target":
                return self._desktop_type_target(step)
            if step.tool == "desktop_hotkey":
                return self._desktop_hotkey(step)
        except Exception as exc:
            return ExecutionResult(success=False, message=f"Execution failed: {exc}")

        return ExecutionResult(success=False, message=f"Unsupported action {step.tool}.")

    def _copy_file(self, step: PlanStep) -> ExecutionResult:
        paths = self._resolve_file_action_paths(step)
        if paths is None:
            return self._missing_paths_result("copy")
        source, destination = paths
        validation = self._validate_source_destination(source, destination)
        if validation is not None:
            return validation

        shutil.copy2(source, destination)
        return ExecutionResult(
            success=True,
            message=f"Copied {source} to {destination}.",
            details=[f"Source: {source}", f"Destination: {destination}"],
        )

    def _move_file(self, step: PlanStep) -> ExecutionResult:
        paths = self._resolve_file_action_paths(step)
        if paths is None:
            return self._missing_paths_result("move")
        source, destination = paths
        validation = self._validate_source_destination(source, destination)
        if validation is not None:
            return validation

        shutil.move(str(source), str(destination))
        return ExecutionResult(
            success=True,
            message=f"Moved {source} to {destination}.",
            details=[f"Source: {source}", f"Destination: {destination}"],
        )

    def _rename_file(self, step: PlanStep) -> ExecutionResult:
        paths = self._resolve_file_action_paths(step)
        if paths is None:
            return self._missing_paths_result("rename")
        source, destination = paths
        validation = self._validate_source_destination(source, destination)
        if validation is not None:
            return validation

        source.rename(destination)
        return ExecutionResult(
            success=True,
            message=f"Renamed {source} to {destination}.",
            details=[f"Source: {source}", f"Destination: {destination}"],
        )

    def _resolve_file_action_paths(self, step: PlanStep) -> tuple[Path, Path] | None:
        source = step.metadata.get("source_path")
        destination = step.metadata.get("destination_path")
        if not source or not destination:
            return None
        return Path(source).expanduser(), Path(destination).expanduser()

    def _validate_source_destination(self, source: Path, destination: Path) -> ExecutionResult | None:
        if not source.exists():
            return ExecutionResult(success=False, message=f"Source not found: {source}")
        if not source.is_file():
            return ExecutionResult(success=False, message=f"Source is not a file: {source}")
        if destination.exists():
            return ExecutionResult(
                success=False,
                message=f"Destination already exists: {destination}",
                details=["Refusing to overwrite an existing file."],
            )
        if not destination.parent.exists():
            return ExecutionResult(
                success=False,
                message=f"Destination folder not found: {destination.parent}",
                details=["Create the destination folder first or choose an existing folder."],
            )
        return None

    def _missing_paths_result(self, action: str) -> ExecutionResult:
        return ExecutionResult(
            success=False,
            message=f"File {action} execution needs explicit source and destination paths.",
            details=['Use quoted paths, for example: copy "C:\\source.txt" to "C:\\target.txt".'],
        )

    def _desktop_click(self, step: PlanStep) -> ExecutionResult:
        if not {"x", "y"}.issubset(step.metadata):
            return ExecutionResult(
                success=False,
                message="Desktop click needs explicit x and y coordinates.",
                details=['Use a request like: click x=420 y=260.'],
            )

        pyautogui = self._load_pyautogui()
        x = int(step.metadata["x"])
        y = int(step.metadata["y"])
        pyautogui.click(x=x, y=y)
        return ExecutionResult(success=True, message=f"Clicked x={x}, y={y}.")

    def _desktop_click_target(self, step: PlanStep) -> ExecutionResult:
        if not {"x", "y"}.issubset(step.metadata):
            target_text = step.metadata.get("target_text")
            if not target_text:
                return ExecutionResult(
                    success=False,
                    message="Visible target click needs explicit quoted text.",
                    details=['Use a request like: click "Save".'],
                )
            target = self._resolve_visible_target(str(target_text))
            if target is None:
                return ExecutionResult(
                    success=False,
                    message=f"No visible UI target resolved for '{target_text}'.",
                    details=["Execution refused because no exact click point is available."],
                )
            step.metadata.update({"x": target.center[0], "y": target.center[1]})

        click_result = self._desktop_click(step)
        if not click_result.success:
            return click_result

        label = step.metadata.get("resolved_label") or step.metadata.get("target_text")
        return ExecutionResult(
            success=True,
            message=f"Clicked visible target '{label}' at x={step.metadata['x']}, y={step.metadata['y']}.",
        )

    def _desktop_type(self, step: PlanStep) -> ExecutionResult:
        text = step.metadata.get("text")
        if not text:
            return ExecutionResult(
                success=False,
                message="Desktop type needs explicit quoted text.",
                details=['Use a request like: type "hello" into the focused field.'],
            )

        pyautogui = self._load_pyautogui()
        pyautogui.write(str(text), interval=0.01)
        return ExecutionResult(success=True, message=f"Typed {len(str(text))} character(s).")

    def _desktop_type_target(self, step: PlanStep) -> ExecutionResult:
        if not step.metadata.get("text"):
            return ExecutionResult(
                success=False,
                message="Target typing needs explicit quoted text.",
                details=['Use a request like: type "Piyush" into "Name".'],
            )

        if not {"x", "y"}.issubset(step.metadata):
            target_text = step.metadata.get("target_text")
            if not target_text:
                return ExecutionResult(
                    success=False,
                    message="Target typing needs explicit quoted target text.",
                    details=['Use a request like: type "Piyush" into "Name".'],
                )
            target = self._resolve_visible_target(str(target_text))
            if target is None:
                return ExecutionResult(
                    success=False,
                    message=f"No visible UI target resolved for '{target_text}'.",
                    details=["Execution refused because no exact focus point is available."],
                )
            step.metadata.update(
                {
                    "resolved_label": target.label,
                    "resolved_control_type": target.control_type,
                    "x": target.center[0],
                    "y": target.center[1],
                    "bounds": list(target.bounds),
                }
            )

        pyautogui = self._load_pyautogui()
        x = int(step.metadata["x"])
        y = int(step.metadata["y"])
        text = str(step.metadata["text"])
        pyautogui.click(x=x, y=y)
        pyautogui.write(text, interval=0.01)

        label = step.metadata.get("resolved_label") or step.metadata.get("target_text")
        return ExecutionResult(
            success=True,
            message=f"Focused visible target '{label}' and typed {len(text)} character(s).",
        )

    def _desktop_hotkey(self, step: PlanStep) -> ExecutionResult:
        keys = step.metadata.get("keys")
        if not keys:
            return ExecutionResult(
                success=False,
                message="Desktop hotkey needs explicit key names.",
                details=['Use a request like: press "ctrl+s".'],
            )

        pyautogui = self._load_pyautogui()
        pyautogui.hotkey(*[str(key) for key in keys])
        return ExecutionResult(success=True, message=f"Pressed {' + '.join(keys)}.")

    def _load_pyautogui(self):
        try:
            import pyautogui

            pyautogui.FAILSAFE = True
            pyautogui.PAUSE = 0.05
            return pyautogui
        except ImportError as exc:
            raise RuntimeError("pyautogui is not installed. Run pip install -r requirements.txt.") from exc

    def _resolve_visible_target(self, target_text: str) -> UiTarget | None:
        target_normalized = self._normalize_label(target_text)
        if not target_normalized:
            return None

        try:
            from pywinauto import Desktop

            desktop = Desktop(backend="uia")
            active = desktop.active()
            candidates = []
            for control in active.descendants():
                label = control.window_text()
                normalized = self._normalize_label(label)
                if not normalized:
                    continue
                if normalized == target_normalized:
                    candidates.insert(0, control)
                elif target_normalized in normalized:
                    candidates.append(control)

            if not candidates:
                return None

            control = candidates[0]
            rectangle = control.rectangle()
            left = int(rectangle.left)
            top = int(rectangle.top)
            right = int(rectangle.right)
            bottom = int(rectangle.bottom)
            return UiTarget(
                label=control.window_text(),
                control_type=control.friendly_class_name(),
                bounds=(left, top, right, bottom),
                center=(left + ((right - left) // 2), top + ((bottom - top) // 2)),
            )
        except Exception:
            return None

    def _normalize_label(self, value: str) -> str:
        return " ".join(value.lower().split())
