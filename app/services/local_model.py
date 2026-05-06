from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen


LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1"}


@dataclass(frozen=True)
class LocalModelStatus:
    enabled: bool
    provider: str
    model: str | None
    endpoint: str | None
    available: bool
    message: str


class LocalModelClient:
    def __init__(self) -> None:
        self.provider = os.getenv("LOCAL_MODEL_PROVIDER", "deterministic").strip().lower()
        self.model = os.getenv("LOCAL_MODEL_NAME", "").strip() or None
        self.endpoint = os.getenv("LOCAL_MODEL_ENDPOINT", "http://127.0.0.1:11434").strip()
        self.timeout_seconds = float(os.getenv("LOCAL_MODEL_TIMEOUT_SECONDS", "0.4"))

    def status(self) -> LocalModelStatus:
        if self.provider in {"", "deterministic", "none"}:
            return LocalModelStatus(
                enabled=False,
                provider="deterministic",
                model=None,
                endpoint=None,
                available=True,
                message="Using deterministic local planner. No model endpoint is configured.",
            )

        if self.provider != "ollama":
            return LocalModelStatus(
                enabled=True,
                provider=self.provider,
                model=self.model,
                endpoint=self.endpoint,
                available=False,
                message=f"Unsupported local model provider: {self.provider}.",
            )

        local_error = self._validate_local_endpoint()
        if local_error:
            return LocalModelStatus(
                enabled=True,
                provider=self.provider,
                model=self.model,
                endpoint=self.endpoint,
                available=False,
                message=local_error,
            )

        try:
            payload = self._get_json("/api/tags")
        except (HTTPError, URLError, TimeoutError, OSError) as exc:
            return LocalModelStatus(
                enabled=True,
                provider=self.provider,
                model=self.model,
                endpoint=self.endpoint,
                available=False,
                message=f"Local Ollama endpoint is not reachable: {exc}.",
            )

        available_models = [item.get("name") for item in payload.get("models", []) if item.get("name")]
        if self.model and self.model not in available_models:
            return LocalModelStatus(
                enabled=True,
                provider=self.provider,
                model=self.model,
                endpoint=self.endpoint,
                available=False,
                message=f"Local model '{self.model}' is not installed in Ollama.",
            )

        return LocalModelStatus(
            enabled=True,
            provider=self.provider,
            model=self.model,
            endpoint=self.endpoint,
            available=True,
            message="Local Ollama endpoint is available.",
        )

    def _validate_local_endpoint(self) -> str | None:
        parsed = urlparse(self.endpoint)
        if parsed.scheme not in {"http", "https"}:
            return "Local model endpoint must use http or https."
        if parsed.hostname not in LOCAL_HOSTS:
            return "Refusing non-local model endpoint. Use localhost or 127.0.0.1."
        return None

    def _get_json(self, path: str) -> dict[str, Any]:
        request = Request(f"{self.endpoint.rstrip('/')}{path}", method="GET")
        with urlopen(request, timeout=self.timeout_seconds) as response:
            return json.loads(response.read().decode("utf-8"))
