"""
Deterministic planner — with compound-instruction chaining.

A single instruction like:
  "Open Notepad, type Hello World, then save it"
produces 3 linked PlanSteps with sequence_index + depends_on set.
"""
from __future__ import annotations

import re
from pathlib import Path

from app.core.intent import extract_quoted_text, infer_mode
from app.core.safety import assess_plan_risk, assess_step_risk
from app.models.schemas import Plan, PlanStep, RequestMode, StepStatus, UserRequest

_CHAIN_RE = re.compile(
    r"\s*(?:,\s*(?:and\s+)?then|;\s*(?:and\s+)?then|,\s*after\s+that"
    r")\s*",
    re.IGNORECASE,
)


def split_compound(text: str) -> list[str]:
    parts = _CHAIN_RE.split(text)
    cleaned = [p.strip() for p in parts if p.strip()]
    return cleaned if len(cleaned) > 1 else [text.strip()]


class Planner:
    def build_plan(self, request: UserRequest) -> Plan:
        segments = split_compound(request.text)
        if len(segments) > 1:
            return self._build_chain_plan(segments, request)
        return self._build_single_plan(request.text, request)

    def _build_chain_plan(self, segments: list[str], request: UserRequest) -> Plan:
        steps: list[PlanStep] = []
        prev_id: str | None = None
        for idx, segment in enumerate(segments):
            seg_steps = self._steps_for_segment(segment)
            for step in seg_steps:
                step.sequence_index = idx
                step.depends_on = prev_id
                if step.tool == "file_search":
                    step.result_key = "last_file_path"
                elif step.tool == "screen_inspect":
                    step.result_key = "last_window_title"
                elif step.tool == "app_open":
                    step.result_key = "last_app"
                steps.append(step)
                prev_id = step.id
        self._link_context_targets(steps)
        risk_assessment = assess_plan_risk(steps)
        n = len(segments)
        summary = (
            f"I planned a {n}-step chain. "
            + ("Pausing before any state-changing action." if risk_assessment.requires_confirmation
               else "All steps are read-only — executing immediately.")
        )
        return Plan(
            summary=summary,
            steps=steps,
            requires_confirmation=risk_assessment.requires_confirmation,
            risk_assessment=risk_assessment,
            is_chain=True,
        )

    def _link_context_targets(self, steps: list[PlanStep]) -> None:
        produced: set[str] = set()
        for step in steps:
            if (
                step.tool in {"document_read", "app_open"}
                and step.target in {"", "general request"}
                and "last_file_path" in produced
            ):
                step.target = "{last_file_path}"
                step.preview = (step.preview or "") + " [target resolved from previous step]"
            if step.result_key:
                produced.add(step.result_key)

    def _build_single_plan(self, text: str, request: UserRequest) -> Plan:
        mode = infer_mode(request)
        steps = self._steps_for_segment(text)
        if not steps:
            fallback_tool = "assistant_answer" if mode == RequestMode.ASK else "screen_inspect"
            steps.append(self._make_step(
                description="Interpret request and gather local context",
                tool=fallback_tool,
                target="general request",
                preview="Will gather context and return a safe next action.",
            ))
        risk_assessment = assess_plan_risk(steps)
        summary = self._build_summary(steps, mode)
        return Plan(
            summary=summary,
            steps=steps,
            requires_confirmation=risk_assessment.requires_confirmation,
            risk_assessment=risk_assessment,
            is_chain=False,
        )

    def _steps_for_segment(self, text: str) -> list[PlanStep]:
        text_lower = text.lower()
        steps: list[PlanStep] = []

        if any(w in text_lower for w in ("find", "search", "latest", "newest")):
            target = self._extract_target(text)
            steps.append(self._make_step(
                description=f"Search local files for '{target}'",
                tool="file_search",
                target=target,
                preview="Will search Desktop, Documents, Downloads and return matching files.",
            ))

        if any(w in text_lower for w in ("read", "summarize", "explain")):
            target = self._extract_target(text)
            steps.append(self._make_step(
                description=f"Read and preview '{target}'",
                tool="document_read",
                target=target,
                preview="Will parse the document and return a readable preview.",
            ))

        if ("open" in text_lower or "launch" in text_lower) and not any(
            w in text_lower for w in ("read", "summarize", "explain")
        ):
            target = self._extract_target(text)
            steps.append(self._make_step(
                description=f"Open '{target}'",
                tool="app_open",
                target=target,
                preview="Will resolve and open the file or app after confirmation.",
            ))

        if any(w in text_lower for w in ("rename", "move", "copy", "delete")):
            target = self._extract_target(text)
            tool = self._detect_file_action(text_lower)
            metadata = self._extract_file_action_metadata(text, tool)
            description = f"{tool.replace('_', ' ').title()}: '{target}'"
            preview = "Will show the exact change before execution."
            if metadata.get("source_path") and metadata.get("destination_path"):
                target = metadata["source_path"]
                description = (
                    f"{tool.replace('_',' ').title()}: "
                    f"'{metadata['source_path']}' → '{metadata['destination_path']}'"
                )
                preview = f"Source: {metadata['source_path']} | Dest: {metadata['destination_path']}"
            steps.append(self._make_step(
                description=description, tool=tool, target=target,
                preview=preview, metadata=metadata,
            ))

        if "screen" in text_lower or "on screen" in text_lower:
            steps.append(self._make_step(
                description="Inspect active screen content",
                tool="screen_inspect",
                target="active screen",
                preview="Will capture window metadata and visible text.",
            ))

        desktop_step = self._build_desktop_action_step(text, text_lower)
        if desktop_step is not None:
            steps.append(desktop_step)

        return steps

    def _build_desktop_action_step(self, text: str, text_lower: str) -> PlanStep | None:
        if re.search(r"\bsave\b", text_lower):
            return self._make_step(
                description="Save current document (Ctrl+S)",
                tool="desktop_hotkey",
                target="ctrl+s",
                preview="Will press Ctrl+S in the active window after confirmation.",
                metadata={"keys": ["ctrl", "s"]},
            )

        if "click" in text_lower:
            metadata = self._extract_click_metadata(text)
            if metadata:
                return self._make_step(
                    description=f"Click at ({metadata['x']}, {metadata['y']})",
                    tool="desktop_click",
                    target=f"{metadata['x']},{metadata['y']}",
                    preview=f"Will click x={metadata['x']}, y={metadata['y']} after confirmation.",
                    metadata=metadata,
                )
            quoted = extract_quoted_text(text)
            if quoted:
                t = quoted[0]
                return self._make_step(
                    description=f"Click visible UI element '{t}'",
                    tool="desktop_click_target",
                    target=t,
                    preview="Will resolve and click the named UI element after confirmation.",
                    metadata={"target_text": t},
                )
            return self._make_step(
                description="Click at screen coordinates",
                tool="desktop_click",
                target="screen coordinates",
                preview="Will click the specified coordinates after confirmation.",
            )

        if any(w in text_lower for w in ("type", "enter text", "write text")):
            meta2 = self._extract_type_into_target_metadata(text)
            if meta2:
                return self._make_step(
                    description=f"Type '{meta2['text']}' into '{meta2['target_text']}'",
                    tool="desktop_type_target",
                    target=meta2["target_text"],
                    preview="Will focus the named field and type the text after confirmation.",
                    metadata=meta2,
                )
            meta1 = self._extract_type_metadata(text)
            t = meta1.get("text", "")
            preview = f"Will type '{t[:40]}{'…' if len(t)>40 else ''}' into the focused control."
            return self._make_step(
                description=f"Type '{t[:30]}{'…' if len(t)>30 else ''}'",
                tool="desktop_type",
                target="focused control",
                preview=preview,
                metadata=meta1,
            )

        if any(w in text_lower for w in ("hotkey", "shortcut", "press")):
            meta = self._extract_hotkey_metadata(text)
            keys = meta.get("keys", [])
            return self._make_step(
                description=f"Press {'+'.join(keys) if keys else '?'}",
                tool="desktop_hotkey",
                target="+".join(keys) or "keyboard",
                preview=f"Will press {' + '.join(keys)} after confirmation." if keys else "Will press the key.",
                metadata=meta,
            )

        return None

    def _extract_target(self, text: str) -> str:
        quoted = extract_quoted_text(text)
        if quoted:
            return quoted[0]
        words = text.split()
        return text if len(words) <= 4 else " ".join(words[1:6])

    def _detect_file_action(self, text_lower: str) -> str:
        for kw, tool in (("rename","file_rename"),("move","file_move"),("copy","file_copy"),("delete","file_delete")):
            if kw in text_lower:
                return tool
        return "file_write"

    def _extract_file_action_metadata(self, text: str, tool: str) -> dict[str, str]:
        if tool == "file_delete":
            return {}
        quoted = extract_quoted_text(text)
        if len(quoted) >= 2:
            src, dst = quoted[0], quoted[1]
            if tool == "file_rename":
                dp = Path(dst)
                if not dp.is_absolute() and dp.parent == Path("."):
                    dst = str(Path(src).expanduser().with_name(dst))
            return {"source_path": src, "destination_path": dst}
        return {}

    def _extract_click_metadata(self, text: str) -> dict[str, int]:
        m = re.search(r"\b(?:x\s*=?\s*)?(-?\d{1,5})\s*[, ]\s*(?:y\s*=?\s*)?(-?\d{1,5})\b", text, re.I)
        return {"x": int(m.group(1)), "y": int(m.group(2))} if m else {}

    def _extract_type_metadata(self, text: str) -> dict[str, str]:
        q = extract_quoted_text(text)
        return {"text": q[0]} if q else {}

    def _extract_type_into_target_metadata(self, text: str) -> dict[str, str]:
        q = extract_quoted_text(text)
        if len(q) < 2 or " into " not in text.lower():
            return {}
        return {"text": q[0], "target_text": q[1]}

    def _extract_hotkey_metadata(self, text: str) -> dict[str, list[str]]:
        q = extract_quoted_text(text)
        raw = q[0] if q else text
        m = re.search(r"\b(?:press|hotkey|shortcut)\s+(.+)$", raw, re.I)
        if m:
            raw = m.group(1)
        keys = [
            self._normalize_key(p)
            for p in re.split(r"\s*(?:\+|,|\band\b)\s*", raw.strip(), flags=re.I)
            if p.strip()
        ]
        return {"keys": keys} if keys else {}

    def _normalize_key(self, key: str) -> str:
        aliases = {"control":"ctrl","ctl":"ctrl","escape":"esc","return":"enter","windows":"win"}
        n = key.strip().lower().replace(" ", "")
        return aliases.get(n, n)

    def _make_step(self, description: str, tool: str, target: str,
                   preview: str, metadata: dict | None = None) -> PlanStep:
        step = PlanStep(
            description=description, tool=tool,
            target=target or str(Path.home()),
            risk_level="low", requires_confirmation=False,
            status=StepStatus.READY, preview=preview,
            metadata=metadata or {},
        )
        risk = assess_step_risk(step)
        step.risk_level = risk.level
        step.risk_score = risk.score
        step.risk_reasons = risk.reasons
        step.requires_confirmation = risk.requires_confirmation
        return step

    def _build_summary(self, steps: list[PlanStep], mode: RequestMode) -> str:
        n = len(steps)
        if mode == RequestMode.ASK:
            return f"Read-only request — planned {n} step(s)."
        if any(s.requires_confirmation for s in steps):
            return f"Planned {n} step(s) — pausing before any state-changing action."
        return f"Planned {n} step(s) — executing immediately (read-only)."
