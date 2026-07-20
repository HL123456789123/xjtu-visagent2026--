"""V1 Chat service exposing only token, recipe_updated, done, and error SSE events."""

from __future__ import annotations

import json
from collections.abc import AsyncGenerator

from app.entity.recipe_schemas import ChatMessageResponse, ChatSessionSummary
from app.repositories.chat_repository import ChatRepository
from app.services.agent_graph import chat_recipe_graph
from app.services.agent_prompts import (
    SSE_EVENT_DONE,
    SSE_EVENT_ERROR,
    SSE_EVENT_RECIPE_UPDATED,
    SSE_EVENT_TOKEN,
)
from app.services.llm_gateway import InvalidLLMOutputError, LLMUnavailableError
from app.services.recipe_service import (
    InvalidRecipeLLMOutputError,
    RecipeLLMUnavailableError,
    RecipeNotFoundError,
    RecipePermissionDeniedError,
    RecipeService,
)


def format_sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False, separators=(',', ':'))}\n\n"


class SessionNotFoundError(RecipeNotFoundError):
    def __init__(self) -> None:
        super().__init__()
        self.message = "会话不存在"
        self.detail = "SESSION_NOT_FOUND"
        self.error_code = "SESSION_NOT_FOUND"


class ChatService:
    def __init__(self, repository: ChatRepository, recipes: RecipeService) -> None:
        self.repository = repository
        self.recipes = recipes

    async def create_session(self, user_id: int, recipe_id: int):
        await self.recipes.get_recipe(recipe_id, user_id)
        return self.repository.create_session(user_id, recipe_id)

    async def list_sessions(self, user_id: int, recipe_id: int) -> list[ChatSessionSummary]:
        await self.recipes.get_recipe(recipe_id, user_id)
        return [self._to_session_summary(session) for session in self.repository.list_sessions_for_recipe(user_id, recipe_id)]

    def list_messages(self, session_id: int, user_id: int) -> list[ChatMessageResponse]:
        self.get_session(session_id, user_id)
        return [
            ChatMessageResponse(
                message_id=message.id,
                role=message.role,
                content=message.content,
                recipe_version=message.recipe_version,
                created_at=message.created_at,
            )
            for message in self.repository.list_messages_for_session(session_id)
        ]

    def get_session(self, session_id: int, user_id: int):
        session = self.repository.get_session(session_id)
        if session is None:
            raise SessionNotFoundError()
        if session.user_id != user_id:
            raise RecipePermissionDeniedError()
        return session

    @staticmethod
    def _to_session_summary(session) -> ChatSessionSummary:
        return ChatSessionSummary(
            session_id=session.id,
            recipe_id=session.recipe_id,
            title=session.title,
            message_count=session.message_count or 0,
            last_message_at=session.last_message_at,
            created_at=session.created_at,
        )

    async def send_message_stream(
        self, session_id: int, user_id: int, content: str
    ) -> AsyncGenerator[str, None]:
        try:
            session = self.get_session(session_id, user_id)
            current = await self.recipes.get_recipe(session.recipe_id, user_id)
            conversation_summary, recent_messages = self.repository.get_conversation_context(
                session_id, recent_limit=12
            )
            user_message = self.repository.save_message(session_id, "user", content)
            current_data = current.model_dump(
                mode="json",
                exclude={
                    "recipe_id",
                    "recognition_id",
                    "version",
                    "nutrition_disclaimer",
                    "generator",
                    "created_at",
                    "updated_at",
                },
            )
            result = await chat_recipe_graph.ainvoke(
                {
                    "current_recipe": current_data,
                    "message": content,
                    "conversation_summary": conversation_summary,
                    "recent_messages": recent_messages,
                    "llm_output": None,
                    "response": {},
                }
            )
            response = result["response"]
            answer = str(response["answer"])
            yield format_sse(SSE_EVENT_TOKEN, {"content": answer})

            updated_version = None
            if response["action"] == "update_recipe":
                updated = await self.recipes.update_recipe(
                    session.recipe_id,
                    user_id,
                    response["recipe"],
                    change_reason=answer,
                    source_message_id=user_message.id,
                )
                updated_version = updated.version
                yield format_sse(
                    SSE_EVENT_RECIPE_UPDATED,
                    {"recipe_id": updated.recipe_id, "version": updated.version},
                )

            message = self.repository.save_message(
                session_id,
                "assistant",
                answer,
                recipe_version=updated_version,
            )
            try:
                self.repository.refresh_context_summary(session_id, recent_limit=12)
            except Exception:
                # 摘要只是后续上下文优化，不能把已保存的对话降级为失败响应。
                pass
            yield format_sse(SSE_EVENT_DONE, {"message_id": message.id})
        except SessionNotFoundError:
            yield format_sse(
                SSE_EVENT_ERROR,
                {"code": "SESSION_NOT_FOUND", "message": "会话不存在"},
            )
        except RecipeNotFoundError:
            yield format_sse(
                SSE_EVENT_ERROR,
                {"code": "RECIPE_NOT_FOUND", "message": "菜谱不存在"},
            )
        except RecipePermissionDeniedError:
            yield format_sse(
                SSE_EVENT_ERROR,
                {"code": "FORBIDDEN", "message": "无权访问该资源"},
            )
        except (InvalidLLMOutputError, InvalidRecipeLLMOutputError, KeyError, TypeError):
            yield format_sse(
                SSE_EVENT_ERROR,
                {"code": "INVALID_LLM_OUTPUT", "message": "模型输出格式不合格"},
            )
        except (LLMUnavailableError, RecipeLLMUnavailableError):
            yield format_sse(
                SSE_EVENT_ERROR,
                {"code": "LLM_UNAVAILABLE", "message": "智能服务暂时不可用"},
            )
        except Exception:
            yield format_sse(
                SSE_EVENT_ERROR,
                {"code": "LLM_UNAVAILABLE", "message": "智能服务暂时不可用"},
            )
