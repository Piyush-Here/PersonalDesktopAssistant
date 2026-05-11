from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates

from app.models.schemas import AssistantReply, ConfirmationRequest, UserRequest
from app.services.assistant_service import assistant_service

router = APIRouter()

# Use absolute path so the server works regardless of working directory
_TEMPLATES_DIR = Path(__file__).parent.parent / "ui" / "templates"
templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))


@router.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    return templates.TemplateResponse("index.html", {"request": request})


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "version": "1.0.0"}


@router.get("/api/model/status")
async def model_status() -> dict[str, object]:
    return asdict(assistant_service.model_status())


@router.get("/api/llm/status")
async def llm_status() -> dict[str, object]:
    """Returns current planner mode and LLM availability."""
    return assistant_service.llm_status()


@router.post("/api/request", response_model=AssistantReply)
async def submit_request(payload: UserRequest) -> AssistantReply:
    try:
        return assistant_service.handle_request(payload)
    except Exception as exc:
        # Return a structured error instead of a 500 traceback
        raise HTTPException(status_code=500, detail=f"Request failed: {exc}") from exc


@router.post("/api/confirm", response_model=AssistantReply)
async def confirm_request(payload: ConfirmationRequest) -> AssistantReply:
    try:
        return assistant_service.confirm_execution(payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Confirmation failed: {exc}") from exc


@router.get("/api/screenshot")
async def take_screenshot() -> dict[str, object]:
    """Capture screen in memory and return a description (no disk write)."""
    result = assistant_service.screenshot.capture()
    return {
        "success": result.success,
        "message": result.message,
        "details": result.details,
    }


@router.get("/api/capabilities")
async def capabilities() -> dict[str, object]:
    """Returns which optional capabilities are available on this machine."""
    caps: dict[str, bool] = {}

    try:
        from PIL import ImageGrab  # noqa: F401
        caps["screenshot"] = True
    except ImportError:
        caps["screenshot"] = False

    try:
        import pyautogui  # noqa: F401
        caps["desktop_actions"] = True
    except ImportError:
        caps["desktop_actions"] = False

    try:
        import pywinauto  # noqa: F401
        caps["ui_automation"] = True
    except ImportError:
        caps["ui_automation"] = False

    try:
        import pytesseract  # noqa: F401
        caps["ocr"] = True
    except ImportError:
        caps["ocr"] = False

    pdf_engine = None
    try:
        import fitz  # noqa: F401
        pdf_engine = "pymupdf"
    except ImportError:
        try:
            from pypdf import PdfReader  # noqa: F401
            pdf_engine = "pypdf"
        except ImportError:
            pass
    caps["pdf_engine"] = pdf_engine  # type: ignore[assignment]

    return caps
