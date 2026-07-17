"""V1 Chat API。"""

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy.orm import Session

from app.core.exceptions import PermissionDeniedError, RecipeNotFoundError
from app.core.security import get_current_user
from app.database.session import get_db
from app.entity.db_models import User
from app.entity.recipe_schema import CreateChatSessionRequest, SendChatMessageRequest
from app.entity.schemas import ApiResponse
from app.repositories.recipe_repository import RecipeRepository
from app.services.chat_repository import chat_repository
from app.services.chat_service import ChatService
from app.services.recipe_service import RecipeService

router = APIRouter(prefix="/api/chat", tags=["菜谱对话"])


def get_chat_service(db: Session = Depends(get_db)) -> ChatService:
    return ChatService(chat_repository, RecipeService(RecipeRepository(db)))


def _error(status_code: int, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"code": status_code, "message": message, "data": None},
    )


@router.post("/sessions", response_model=ApiResponse, status_code=status.HTTP_201_CREATED)
async def create_session(
    body: CreateChatSessionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    service: ChatService = Depends(get_chat_service),
):
    try:
        session = await service.create_session(db, current_user.id, body.recipe_id)
    except RecipeNotFoundError as exc:
        return _error(404, exc.message)
    except PermissionDeniedError as exc:
        return _error(403, exc.message)
    return ApiResponse(
        code=201,
        message="会话创建成功",
        data={
            "session_id": session.id,
            "recipe_id": session.recipe_id,
            "created_at": session.created_at.isoformat(),
        },
    )


@router.post("/sessions/{session_id}/messages")
async def send_message(
    session_id: int,
    body: SendChatMessageRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    service: ChatService = Depends(get_chat_service),
):
    try:
        service.get_session(db, session_id, current_user.id)
    except RecipeNotFoundError as exc:
        return _error(404, exc.message)
    return StreamingResponse(
        service.send_message_stream(db, session_id, current_user.id, body.content),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
