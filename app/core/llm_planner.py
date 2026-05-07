"""
LLM-backed planner using a local Ollama model.

Converts free-form English instructions into structured tool-call JSON,
then builds a Plan the same way the deterministic planner does.
Falls back to the deterministic planner on any parse failure.
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from app.core.planner import Planner
from app.core.safety import assess_plan_risk, assess_step_risk
from app.models.schemas import Plan, PlanStep, RequestMode, StepStatus, UserRequest

log = logging.getLogger(__name__)

LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1"}

# ── System prompt given to the local model ────────────────────────────────────
_SYSTEM_PROMPT = """
You are a planner for a Windows desktop assistant.
Your only job is to convert a user's English instruction into a JSON array of tool-call objects.

Available tools:
  file_search        – search local files  {target: string}
  document_read      – read/summarize a file  {target: string}
  app_open           – open a file or app  {target: string}
  file_copy          – copy a file  {source_path: string, destination_path: string}
  file_move          – move a file  {source_path: string, destination_path: string}
  file_rename        – rename a file  {source_path: string, destination_path: string}
  screen_inspect     – inspect the active screen  {}
  desktop_click      – click by coordinates  {x: int, y: int}
  desktop_click_target – click a visible UI element by label  {target_text: string}
  desktop_type       – type text into focused control  {text: string}
  desktop_type_target – type text into a named field  {text: string, target_text: string}
  desktop_hotkey     – press a key or hotkey  {keys: [string]}

Rules:
1. Respond with ONLY a valid JSON array, no prose, no markdown fences.
2. Each element must be {"tool": "<name>", "description": "<short description>", "metadata": {<params>}}.
3. Use only the tools listed above.
4. If the instruction is a pure question or read-only request, prefer file_search + document_read.
5. Do not invent file paths unless the user explicitly stated them.
6. If you cannot map the instruction to any tool, return [{"tool":"assistant_answer","description":"Could not map to a specific tool","metadata":{}}].
""".strip()


class LLMPlanner:
    """
    Tries to use the configured local Ollama model to build a plan.
    On any failure, transparently delegates to the deterministic Planner.
    """

    def __init__(self) -> None:
        self.provider = os.getenv("LOCAL_MODEL_PROVIDER", "deterministic").strip().lower()
        self.model = os.getenv("LOCAL_MODEL_NAME", "llama3.1").strip()
        self.endpoint = os.getenv("LOCAL_MODEL_ENDPOINT", "http://127.0.0.1:11434").strip()
        self.timeout = float(os.getenv("LOCAL_MODEL_TIMEOUT_SECONDS", "30"))
        self._fallback = Planner()

    # ── Public API ─────────────────────────────────────────────────────────────

    def build_plan(self, request: UserRequest) -> Plan:
        if self.provider not in {"ollama"}:
            return self._fallback.build_plan(request)

        if not self._endpoint_is_local():
            log.warning("Non-local Ollama endpoint refused; using deterministic planner.")
            return self._fallback.build_plan(request)

        raw_steps = self._call_ollama(request.text)
        if raw_steps is None:
            return self._fallback.build_plan(request)

        plan = self._build_plan_from_steps(raw_steps, request)
        if plan is None:
            return self._fallback.build_plan(request)

        return plan

    @property
    def using_llm(self) -> bool:
        return self.provider == "ollama" and self._endpoint_is_local()

    # ── Private helpers ────────────────────────────────────────────────────────

    def _endpoint_is_local(self) -> bool:
        try:
            parsed = urlparse(self.endpoint)
            return parsed.hostname in LOCAL_HOSTS
        except Exception:
            return False

    def _call_ollama(self, user_text: str) -> list[dict[str, Any]] | None:
        payload = json.dumps(
            {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": user_text},
                ],
                "stream": False,
                "format": "json",
                "options": {"temperature": 0.0},
            }
        ).encode()

        req = Request(
            f"{self.endpoint.rstrip('/')}/api/chat",
            data=payload,
            method="POST",
            headers={"Content-Type": "application/json"},
        )

        try:
            with urlopen(req, timeout=self.timeout) as resp:
                body = json.loads(resp.read().decode())
        except (HTTPError, URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
            log.warning("Ollama call failed (%s); falling back to deterministic planner.", exc)
            return None

        try:
            content = body["message"]["content"]
            parsed = json.loads(content)
            if isinstance(parsed, list):
                return parsed
            # Ollama sometimes wraps in {"steps": [...]}
            for key in ("steps", "tools", "plan"):
                if isinstance(parsed.get(key), list):
                    return parsed[key]
            log.warning("Unexpected Ollama JSON shape; falling back.")
            return None
        except (KeyError, json.JSONDecodeError, TypeError) as exc:
            log.warning("Could not parse Ollama response (%s); falling back.", exc)
            return None

    def _build_plan_from_steps(
        self, raw_steps: list[dict[str, Any]], request: UserRequest
    ) -> Plan | None:
        known_tools = {
            "file_search", "document_read", "app_open",
            "file_copy", "file_move", "file_rename",
            "screen_inspect", "desktop_click", "desktop_click_target",
            "desktop_type", "desktop_type_target", "desktop_hotkey",
            "assistant_answer",
        }

        steps: list[PlanStep] = []
        for raw in raw_steps:
            tool = raw.get("tool", "").strip()
            if tool not in known_tools:
                log.warning("LLM returned unknown tool '%s'; skipping.", tool)
                continue

            description = str(raw.get("description", tool))
            metadata: dict[str, Any] = raw.get("metadata", {}) or {}

            # Derive target string from metadata or description
            target = (
                metadata.get("target")
                or metadata.get("target_text")
                or metadata.get("source_path")
                or description
            )

            step = PlanStep(
                description=description,
                tool=tool,
                target=str(target),
                risk_level="low",
                requires_confirmation=False,
                status=StepStatus.READY,
                preview=f"LLM-planned: {description}",
                metadata=metadata,
            )
            risk = assess_step_risk(step)
            step.risk_level = risk.level
            step.risk_score = risk.score
            step.risk_reasons = risk.reasons
            step.requires_confirmation = risk.requires_confirmation
            steps.append(step)

        if not steps:
            return None

        risk_assessment = assess_plan_risk(steps)
        mode = request.mode
        n = len(steps)
        if any(s.requires_confirmation for s in steps):
            summary = f"LLM planned {n} step(s) and paused before any state-changing action."
        else:
            summary = f"LLM planned {n} step(s) for read-only execution."

        return Plan(
            summary=summary,
            steps=steps,
            requires_confirmation=risk_assessment.requires_confirmation,
            risk_assessment=risk_assessment,
        )
