from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.models.schemas import AssistantReply, ConfirmationRequest, UserRequest
from app.services.assistant_service import assistant_service

router = APIRouter()
templates = Jinja2Templates(directory="app/ui/templates")


@router.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    return templates.TemplateResponse("index.html", {"request": request})


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.post("/api/request", response_model=AssistantReply)
async def submit_request(payload: UserRequest) -> AssistantReply:
    return assistant_service.handle_request(payload)


@router.post("/api/confirm", response_model=AssistantReply)
async def confirm_request(payload: ConfirmationRequest) -> AssistantReply:
    try:
        return assistant_service.confirm_execution(payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
