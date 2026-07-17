"""V1 菜谱对话服务，仅产生 token/recipe_updated/done/error 四类 SSE。"""

import json
from collections.abc import AsyncGenerator

from sqlalchemy.orm import Session

from app.core.exceptions import PermissionDeniedError, RecipeNotFoundError
from app.services.agent_graph import chat_recipe_graph
from app.services.chat_repository import ChatRepository, chat_repository
from app.services.llm_gateway import InvalidLLMOutputError, LLMUnavailableError
from app.services.recipe_service import RecipeService


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


class ChatService:
    def __init__(
        self,
        repository: ChatRepository,
        recipes: RecipeService,
    ):
        self.repository = repository
        self.recipes = recipes

    async def create_session(self, db: Session, user_id: int, recipe_id: int):
        await self.recipes.get_recipe(recipe_id, user_id)
        return self.repository.create_session(db, user_id, recipe_id)

    def get_session(self, db: Session, session_id: int, user_id: int):
        session = self.repository.get_session_for_user(db, session_id, user_id)
        if session is None:
            raise RecipeNotFoundError("会话不存在")
        return session

    async def send_message_stream(
        self, db: Session, session_id: int, user_id: int, content: str
    ) -> AsyncGenerator[str, None]:
        session = self.get_session(db, session_id, user_id)
        try:
            current = await self.recipes.get_recipe(session.recipe_id, user_id)
            self.repository.save_message(db, session_id, "user", content)
            current_data = current.model_dump(
                mode="json",
                exclude={
                    "recipe_id", "recognition_id", "version", "nutrition_disclaimer",
                    "generator", "created_at", "updated_at",
                },
            )
            result = await chat_recipe_graph.ainvoke(
                {
                    "current_recipe": current_data,
                    "message": content,
                    "llm_output": None,
                    "response": {},
                }
            )
            response = result["response"]
            answer = response["answer"]
            yield _sse("token", {"content": answer})

            if response["action"] == "update_recipe":
                updated = await self.recipes.update_recipe(
                    session.recipe_id, user_id, response["recipe"]
                )
                yield _sse(
                    "recipe_updated",
                    {"recipe_id": updated.recipe_id, "version": updated.version},
                )

            message = self.repository.save_message(db, session_id, "assistant", answer)
            yield _sse("done", {"message_id": message.id})
        except (RecipeNotFoundError, PermissionDeniedError):
            yield _sse("error", {"code": "NOT_FOUND", "message": "菜谱或会话不存在"})
        except InvalidLLMOutputError:
            yield _sse("error", {"code": "INVALID_LLM_OUTPUT", "message": "模型输出格式不合格"})
        except LLMUnavailableError:
            yield _sse("error", {"code": "LLM_UNAVAILABLE", "message": "智能服务暂时不可用"})
        except Exception:
            yield _sse("error", {"code": "LLM_UNAVAILABLE", "message": "智能服务暂时不可用"})
