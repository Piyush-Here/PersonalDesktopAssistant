"""
Screenshot tool — captures the active screen in memory and optionally
sends it to a local vision-capable Ollama model for a natural-language
description of what is visible.

No screenshot is ever saved to disk unless the user explicitly requests it.
"""
from __future__ import annotations

import base64
import io
import json
import logging
import os
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from app.models.schemas import ExecutionResult

log = logging.getLogger(__name__)

LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1"}

_VISION_PROMPT = (
    "You are a screen-reader assistant. "
    "Describe what you see on this desktop screenshot concisely: "
    "what application is in focus, what UI controls are visible, "
    "and any important text that is displayed. "
    "Keep your description under 200 words."
)


class ScreenshotTool:
    """
    Captures the screen in memory.
    If a vision-capable Ollama model is configured it will also
    return an AI-generated description of the screen contents.
    """

    def __init__(self) -> None:
        self.provider = os.getenv("LOCAL_MODEL_PROVIDER", "deterministic").strip().lower()
        self.model = os.getenv("LOCAL_VISION_MODEL_NAME", os.getenv("LOCAL_MODEL_NAME", "llava")).strip()
        self.endpoint = os.getenv("LOCAL_MODEL_ENDPOINT", "http://127.0.0.1:11434").strip()
        self.timeout = float(os.getenv("LOCAL_MODEL_TIMEOUT_SECONDS", "30"))

    # ── Public API ─────────────────────────────────────────────────────────────

    def capture(self) -> ExecutionResult:
        """Capture and optionally describe the current screen."""
        png_bytes = self._grab_screenshot()
        if png_bytes is None:
            return ExecutionResult(
                success=False,
                message="Screenshot capture failed. Is Pillow installed?",
                details=["pip install pillow"],
            )

        details: list[str] = []
        size_info = self._image_size(png_bytes)
        details.append(f"Screenshot captured in memory: {size_info}.")
        details.append("Screenshot was NOT saved to disk.")

        description = self._describe_with_vision(png_bytes)
        if description:
            details.append("─── Vision model description ───")
            details.extend(description.strip().splitlines())
        else:
            details.append("Vision description unavailable (no vision model configured or reachable).")

        return ExecutionResult(
            success=True,
            message="Screen captured successfully.",
            details=details,
        )

    def capture_as_base64(self) -> tuple[str, str] | None:
        """Return (base64_png, size_string) or None if capture failed."""
        png_bytes = self._grab_screenshot()
        if png_bytes is None:
            return None
        b64 = base64.b64encode(png_bytes).decode()
        size = self._image_size(png_bytes)
        return b64, size

    # ── Private helpers ────────────────────────────────────────────────────────

    def _grab_screenshot(self) -> bytes | None:
        try:
            from PIL import ImageGrab

            img = ImageGrab.grab()
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            return buf.getvalue()
        except ImportError:
            log.warning("Pillow is not installed; cannot capture screenshot.")
            return None
        except Exception as exc:
            log.warning("Screenshot capture failed: %s", exc)
            return None

    def _image_size(self, png_bytes: bytes) -> str:
        try:
            from PIL import Image

            img = Image.open(io.BytesIO(png_bytes))
            return f"{img.width}x{img.height}"
        except Exception:
            return f"{len(png_bytes)} bytes"

    def _describe_with_vision(self, png_bytes: bytes) -> str | None:
        if self.provider != "ollama":
            return None
        if not self._endpoint_is_local():
            return None

        b64 = base64.b64encode(png_bytes).decode()
        payload = json.dumps(
            {
                "model": self.model,
                "messages": [
                    {
                        "role": "user",
                        "content": _VISION_PROMPT,
                        "images": [b64],
                    }
                ],
                "stream": False,
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
            return body["message"]["content"]
        except (HTTPError, URLError, TimeoutError, OSError, KeyError, json.JSONDecodeError) as exc:
            log.warning("Vision model call failed: %s", exc)
            return None

    def _endpoint_is_local(self) -> bool:
        try:
            parsed = urlparse(self.endpoint)
            return parsed.hostname in LOCAL_HOSTS
        except Exception:
            return False
