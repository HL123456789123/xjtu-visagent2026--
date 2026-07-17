"""Authenticated V1 Chat and SSE API."""

from fastapi import APIRouter, Depends, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.database.session import get_db
from app.entity.db_models import User
from app.entity.recipe_schemas import CreateChatSessionRequest, SendChatMessageRequest
from app.entity.schemas import ApiResponse
from app.repositories.chat_repository import ChatRepository
from app.repositories.food_repository import FoodRepository
from app.repositories.recipe_repository import RecipeRepository
from app.services.chat_service import ChatService
from app.services.recipe_service import RecipeService, to_china_time

router = APIRouter(prefix="/api/chat", tags=["菜谱对话"])


def get_chat_service(db: Session = Depends(get_db)) -> ChatService:
    recipes = RecipeService(FoodRepository(db), RecipeRepository(db))
    return ChatService(ChatRepository(db), recipes)


@router.post("/sessions", response_model=ApiResponse, status_code=status.HTTP_201_CREATED)
async def create_chat_session(
    request: CreateChatSessionRequest,
    current_user: User = Depends(get_current_user),
    service: ChatService = Depends(get_chat_service),
):
    session = await service.create_session(current_user.id, request.recipe_id)
    return ApiResponse(
        code=201,
        message="会话创建成功",
        data={
            "session_id": session.id,
            "recipe_id": session.recipe_id,
            "created_at": to_china_time(session.created_at).isoformat(),
        },
    )


@router.post("/sessions/{session_id}/messages")
async def send_chat_message(
    session_id: int,
    request: SendChatMessageRequest,
    current_user: User = Depends(get_current_user),
    service: ChatService = Depends(get_chat_service),
):
    service.get_session(session_id, current_user.id)
    return StreamingResponse(
        service.send_message_stream(session_id, current_user.id, request.content),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
