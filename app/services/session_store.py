from __future__ import annotations

import json
from pathlib import Path

from app.models.schemas import ActionSession


class SessionStore:
    def __init__(self, base_dir: Path) -> None:
        self.base_dir = base_dir
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.sessions: dict[str, ActionSession] = {}

    def save(self, session: ActionSession) -> None:
        self.sessions[session.id] = session
        path = self.base_dir / f"{session.id}.json"
        path.write_text(session.model_dump_json(indent=2), encoding="utf-8")

    def get(self, session_id: str) -> ActionSession:
        if session_id in self.sessions:
            return self.sessions[session_id]

        path = self.base_dir / f"{session_id}.json"
        if not path.exists():
            raise KeyError(f"Session {session_id} not found")

        session = ActionSession.model_validate(json.loads(path.read_text(encoding="utf-8")))
        self.sessions[session_id] = session
        return session
