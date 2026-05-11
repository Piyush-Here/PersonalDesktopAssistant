from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.routes import router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)


def create_app() -> FastAPI:
    app = FastAPI(
        title="Personal Desktop Assistant",
        version="1.0.0",
        description="Windows-first, confirmation-first local AI assistant.",
    )

    # Allow browser requests from the same origin (needed when running behind
    # a dev proxy like VS Code's port forwarding).
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://127.0.0.1:8000", "http://localhost:8000"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(router)

    static_dir = Path(__file__).parent / "ui" / "static"
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    # Ensure the session-store directory exists at startup
    sessions_dir = Path("data") / "sessions"
    sessions_dir.mkdir(parents=True, exist_ok=True)

    @app.on_event("startup")
    async def _startup_log() -> None:  # type: ignore[misc]
        log.info("Personal Desktop Assistant starting up")
        log.info("Open http://127.0.0.1:8000 in your browser")
        _log_capabilities()

    return app


def _log_capabilities() -> None:
    caps = []
    try:
        from PIL import ImageGrab  # noqa: F401
        caps.append("screenshot=yes")
    except ImportError:
        caps.append("screenshot=no (pip install pillow)")

    try:
        import pyautogui  # noqa: F401
        caps.append("desktop_actions=yes")
    except ImportError:
        caps.append("desktop_actions=no (pip install pyautogui)")

    try:
        import pywinauto  # noqa: F401
        caps.append("ui_automation=yes")
    except ImportError:
        caps.append("ui_automation=no (pip install pywinauto)")

    try:
        import fitz  # noqa: F401
        caps.append("pdf=pymupdf")
    except ImportError:
        try:
            from pypdf import PdfReader  # noqa: F401
            caps.append("pdf=pypdf")
        except ImportError:
            caps.append("pdf=none (pip install pymupdf)")

    log.info("Capabilities: %s", " | ".join(caps))


app = create_app()
