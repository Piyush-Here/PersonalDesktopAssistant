from __future__ import annotations

import re

from app.models.schemas import RequestMode, UserRequest


READ_ONLY_HINTS = (
    "read",
    "summarize",
    "show",
    "find",
    "search",
    "what is",
    "list",
    "explain",
)

WRITE_HINTS = (
    "delete",
    "remove",
    "rename",
    "move",
    "copy",
    "open",
    "close",
    "send",
    "create",
    "write",
    "edit",
    "launch",
)


def infer_mode(request: UserRequest) -> RequestMode:
    if request.mode != RequestMode.ACT:
        return request.mode

    text = request.text.lower()
    if any(token in text for token in READ_ONLY_HINTS) and not any(
        token in text for token in WRITE_HINTS
    ):
        return RequestMode.ASK
    return RequestMode.ACT


def extract_quoted_text(text: str) -> list[str]:
    return re.findall(r'"([^"]+)"', text)
