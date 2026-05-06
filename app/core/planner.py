from __future__ import annotations

import re
from pathlib import Path

from app.core.intent import extract_quoted_text, infer_mode
from app.core.safety import assess_plan_risk, assess_step_risk
from app.models.schemas import Plan, PlanStep, RequestMode, StepStatus, UserRequest


class Planner:
    def build_plan(self, request: UserRequest) -> Plan:
        mode = infer_mode(request)
        text = request.text.strip()
        text_lower = text.lower()
        steps: list[PlanStep] = []

        if any(word in text_lower for word in ("find", "search", "latest", "newest")):
            target = self._extract_target(text)
            steps.append(
                self._make_step(
                    description=f"Search local files for {target}",
                    tool="file_search",
                    target=target,
                    preview="Will inspect indexed folders and return matching files.",
                )
            )

        if any(word in text_lower for word in ("read", "summarize", "explain")):
            target = self._extract_target(text)
            steps.append(
                self._make_step(
                    description=f"Read accessible content for {target}",
                    tool="document_read",
                    target=target,
                    preview="Will parse supported document types and summarize their content.",
                )
            )

        if "open" in text_lower or "launch" in text_lower:
            target = self._extract_target(text)
            steps.append(
                self._make_step(
                    description=f"Open application or file {target}",
                    tool="app_open",
                    target=target,
                    preview="Will resolve the file or app path, then wait for confirmation before opening.",
                )
            )

        if any(word in text_lower for word in ("rename", "move", "copy", "delete")):
            target = self._extract_target(text)
            tool = self._detect_file_action(text_lower)
            metadata = self._extract_file_action_metadata(text, tool)
            description = f"Prepare {tool.replace('_', ' ')} operation for {target}"
            preview = "Will gather targets and show the exact change before execution."
            if metadata.get("source_path") and metadata.get("destination_path"):
                target = metadata["source_path"]
                description = (
                    f"Prepare {tool.replace('_', ' ')} from "
                    f"{metadata['source_path']} to {metadata['destination_path']}"
                )
                preview = f"Source: {metadata['source_path']} | Destination: {metadata['destination_path']}"
            steps.append(
                self._make_step(
                    description=description,
                    tool=tool,
                    target=target,
                    preview=preview,
                    metadata=metadata,
                )
            )

        if "screen" in text_lower or "on screen" in text_lower:
            steps.append(
                self._make_step(
                    description="Inspect active screen content",
                    tool="screen_inspect",
                    target="active screen",
                    preview="Will capture current window metadata and screen text when available.",
                )
            )

        desktop_step = self._build_desktop_action_step(text, text_lower)
        if desktop_step is not None:
            steps.append(desktop_step)

        if not steps:
            fallback_tool = "assistant_answer" if mode == RequestMode.ASK else "screen_inspect"
            steps.append(
                self._make_step(
                    description="Interpret request and gather local context",
                    tool=fallback_tool,
                    target="general request",
                    preview="Will gather context conservatively and return a safe next action.",
                )
            )

        risk_assessment = assess_plan_risk(steps)
        confirmation_required = risk_assessment.requires_confirmation
        summary = self._build_summary(steps, mode)
        return Plan(
            summary=summary,
            steps=steps,
            requires_confirmation=confirmation_required,
            risk_assessment=risk_assessment,
        )

    def _extract_target(self, text: str) -> str:
        quoted = extract_quoted_text(text)
        if quoted:
            return quoted[0]
        words = text.split()
        if len(words) <= 4:
            return text
        return " ".join(words[1:6])

    def _detect_file_action(self, text_lower: str) -> str:
        mapping = {
            "rename": "file_rename",
            "move": "file_move",
            "copy": "file_copy",
            "delete": "file_delete",
        }
        for keyword, tool in mapping.items():
            if keyword in text_lower:
                return tool
        return "file_write"

    def _extract_file_action_metadata(self, text: str, tool: str) -> dict[str, str]:
        if tool == "file_delete":
            return {}

        quoted = extract_quoted_text(text)
        if len(quoted) >= 2:
            source = quoted[0]
            destination = quoted[1]
            if tool == "file_rename":
                destination_path = Path(destination)
                if not destination_path.is_absolute() and destination_path.parent == Path("."):
                    destination = str(Path(source).expanduser().with_name(destination))
            return {"source_path": source, "destination_path": destination}

        return {}

    def _build_desktop_action_step(self, text: str, text_lower: str) -> PlanStep | None:
        if "click" in text_lower:
            metadata = self._extract_click_metadata(text)
            if metadata:
                return self._make_step(
                    description="Click explicit screen coordinates",
                    tool="desktop_click",
                    target=f"{metadata['x']},{metadata['y']}",
                    preview=f"Will click x={metadata['x']}, y={metadata['y']} after confirmation.",
                    metadata=metadata,
                )

            quoted = extract_quoted_text(text)
            if quoted:
                target_text = quoted[0]
                return self._make_step(
                    description=f"Resolve and click visible UI target {target_text}",
                    tool="desktop_click_target",
                    target=target_text,
                    preview="Will inspect visible controls, propose a resolved target, and wait for confirmation.",
                    metadata={"target_text": target_text},
                )

            return self._make_step(
                description="Click explicit screen coordinates",
                tool="desktop_click",
                target="screen coordinates",
                preview="Will click the explicit screen coordinates after confirmation.",
                metadata={},
            )

        if any(word in text_lower for word in ("type", "enter text", "write text")):
            metadata = self._extract_type_into_target_metadata(text)
            if metadata:
                return self._make_step(
                    description=f"Resolve visible UI target {metadata['target_text']} and type text",
                    tool="desktop_type_target",
                    target=metadata["target_text"],
                    preview="Will inspect visible controls, focus the resolved target, type quoted text, and wait for confirmation.",
                    metadata=metadata,
                )

            metadata = self._extract_type_metadata(text)
            preview = "Will type the quoted text into the focused control after confirmation."
            if metadata.get("text"):
                preview = f"Will type {len(metadata['text'])} character(s) into the focused control."
            return self._make_step(
                description="Type text into focused control",
                tool="desktop_type",
                target="focused control",
                preview=preview,
                metadata=metadata,
            )

        if any(word in text_lower for word in ("hotkey", "shortcut", "press")):
            metadata = self._extract_hotkey_metadata(text)
            preview = "Will press the explicit key or key combination after confirmation."
            if metadata.get("keys"):
                preview = f"Will press {' + '.join(metadata['keys'])} after confirmation."
            return self._make_step(
                description="Press explicit key or hotkey",
                tool="desktop_hotkey",
                target="+".join(metadata.get("keys", [])) or "keyboard",
                preview=preview,
                metadata=metadata,
            )

        return None

    def _extract_click_metadata(self, text: str) -> dict[str, int]:
        match = re.search(r"\b(?:x\s*=?\s*)?(-?\d{1,5})\s*[, ]\s*(?:y\s*=?\s*)?(-?\d{1,5})\b", text, re.I)
        if not match:
            return {}
        return {"x": int(match.group(1)), "y": int(match.group(2))}

    def _extract_type_metadata(self, text: str) -> dict[str, str]:
        quoted = extract_quoted_text(text)
        if not quoted:
            return {}
        return {"text": quoted[0]}

    def _extract_type_into_target_metadata(self, text: str) -> dict[str, str]:
        quoted = extract_quoted_text(text)
        if len(quoted) < 2 or " into " not in text.lower():
            return {}
        return {"text": quoted[0], "target_text": quoted[1]}

    def _extract_hotkey_metadata(self, text: str) -> dict[str, list[str]]:
        quoted = extract_quoted_text(text)
        raw_keys = quoted[0] if quoted else text
        key_match = re.search(r"\b(?:press|hotkey|shortcut)\s+(.+)$", raw_keys, re.I)
        if key_match:
            raw_keys = key_match.group(1)
        keys = [
            self._normalize_key(part)
            for part in re.split(r"\s*(?:\+|,|\band\b)\s*", raw_keys.strip(), flags=re.I)
            if part.strip()
        ]
        return {"keys": keys} if keys else {}

    def _normalize_key(self, key: str) -> str:
        aliases = {
            "control": "ctrl",
            "ctl": "ctrl",
            "escape": "esc",
            "return": "enter",
            "windows": "win",
        }
        normalized = key.strip().lower().replace(" ", "")
        return aliases.get(normalized, normalized)

    def _make_step(
        self,
        description: str,
        tool: str,
        target: str,
        preview: str,
        metadata: dict[str, str] | None = None,
    ) -> PlanStep:
        step = PlanStep(
            description=description,
            tool=tool,
            target=target or str(Path.home()),
            risk_level="low",
            requires_confirmation=False,
            status=StepStatus.READY,
            preview=preview,
            metadata=metadata or {},
        )
        risk = assess_step_risk(step)
        step.risk_level = risk.level
        step.risk_score = risk.score
        step.risk_reasons = risk.reasons
        step.requires_confirmation = risk.requires_confirmation
        return step

    def _build_summary(self, steps: list[PlanStep], mode: RequestMode) -> str:
        if mode == RequestMode.ASK:
            return f"I interpreted this as a read-only request and prepared {len(steps)} step(s)."
        if any(step.requires_confirmation for step in steps):
            return f"I prepared {len(steps)} step(s) and paused before any state-changing action."
        return f"I prepared {len(steps)} step(s) for immediate execution."
