"""Recipe orchestration through the shared V1 repositories and minimal graph."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from pydantic import ValidationError

from app.core.exceptions import AppException
from app.entity.recipe_schemas import (
    ChatSessionSummary,
    RecipeCreateRequest,
    RecipeGenerateResult,
    RecipeHistoryItem,
    RecipeHistoryPage,
    RecipeResponse,
    RecipeVersionDetail,
    RecipeVersionList,
    RecipeVersionSummary,
)
from app.repositories.chat_repository import ChatRepository
from app.repositories.food_repository import FoodRepository
from app.repositories.recipe_repository import RecipeRepository
from app.services.agent_graph import generate_recipe_graph
from app.services.agent_prompts import NUTRITION_DISCLAIMER
from app.services.llm_gateway import (
    InvalidLLMOutputError,
    LLMUnavailableError,
    get_llm_gateway,
)

CST = timezone(timedelta(hours=8))


def to_china_time(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=CST)
    return value.astimezone(CST)


class RecipeServiceError(AppException):
    def __init__(self, status_code: int, error_code: str, message: str) -> None:
        super().__init__(status_code, message, detail=error_code)
        self.error_code = error_code


class RecognitionNotFoundError(RecipeServiceError):
    def __init__(self) -> None:
        super().__init__(404, "RECOGNITION_NOT_FOUND", "识别记录不存在")


class RecipeNotFoundError(RecipeServiceError):
    def __init__(self) -> None:
        super().__init__(404, "RECIPE_NOT_FOUND", "菜谱不存在")


class RecipeVersionNotFoundError(RecipeServiceError):
    def __init__(self) -> None:
        super().__init__(404, "RECIPE_VERSION_NOT_FOUND", "菜谱版本不存在")


class RecipePermissionDeniedError(RecipeServiceError):
    def __init__(self) -> None:
        super().__init__(403, "FORBIDDEN", "无权访问该资源")


class NoConfirmedIngredientsError(RecipeServiceError):
    def __init__(self) -> None:
        super().__init__(422, "NO_CONFIRMED_INGREDIENTS", "该识别任务尚未确认食材")


class InvalidRecipeLLMOutputError(RecipeServiceError):
    def __init__(self) -> None:
        super().__init__(422, "INVALID_LLM_OUTPUT", "LLM 输出格式不合格")


class RecipeLLMUnavailableError(RecipeServiceError):
    def __init__(self) -> None:
        super().__init__(503, "LLM_UNAVAILABLE", "智能服务暂时不可用")


class RecipeService:
    def __init__(
        self,
        food_repository: FoodRepository,
        recipe_repository: RecipeRepository,
        chat_repository: ChatRepository | None = None,
    ) -> None:
        self.food_repository = food_repository
        self.recipe_repository = recipe_repository
        self.chat_repository = chat_repository

    @staticmethod
    def _to_response(record) -> RecipeResponse:
        return RecipeResponse(
            recipe_id=record.id,
            recognition_id=record.recognition_id,
            version=record.version,
            **record.recipe_data,
            nutrition_disclaimer=NUTRITION_DISCLAIMER,
            generator=record.generator,
            created_at=to_china_time(record.created_at),
            updated_at=to_china_time(record.updated_at),
        )

    async def create_recipe(
        self, request: RecipeCreateRequest, user_id: int
    ) -> RecipeResponse:
        recognition = self.food_repository.get_recognition(request.recognition_id)
        if recognition is None:
            raise RecognitionNotFoundError()
        if recognition.user_id != user_id:
            raise RecipePermissionDeniedError()
        ingredients = self.food_repository.get_confirmed_ingredients(
            request.recognition_id, user_id
        )
        if not ingredients:
            raise NoConfirmedIngredientsError()
        try:
            result = await generate_recipe_graph.ainvoke(
                {
                    "confirmed_ingredients": ingredients,
                    "preferences": request.preferences.model_dump(mode="json"),
                    "raw_recipe": None,
                }
            )
            recipe_data = RecipeGenerateResult.model_validate(result["raw_recipe"])
            gateway = get_llm_gateway()
        except (InvalidLLMOutputError, ValidationError, KeyError, TypeError, ValueError) as exc:
            raise InvalidRecipeLLMOutputError() from exc
        except LLMUnavailableError as exc:
            raise RecipeLLMUnavailableError() from exc

        record = self.recipe_repository.create_recipe(
            user_id,
            request.recognition_id,
            recipe_data.model_dump(mode="json"),
            gateway.generator,
        )
        return self._to_response(record)

    async def get_recipe(self, recipe_id: int, user_id: int) -> RecipeResponse:
        record = self.recipe_repository.get_recipe(recipe_id)
        if record is None:
            raise RecipeNotFoundError()
        if record.user_id != user_id:
            raise RecipePermissionDeniedError()
        return self._to_response(record)

    async def list_history(
        self, user_id: int, *, page: int, page_size: int
    ) -> RecipeHistoryPage:
        records, total = self.recipe_repository.list_recipes_for_user(
            user_id, page=page, page_size=page_size
        )
        items: list[RecipeHistoryItem] = []
        for record in records:
            recognition = self.food_repository.get_recognition_for_user(
                record.recognition_id, user_id
            )
            if recognition is None:
                continue
            latest_session = (
                self.chat_repository.get_latest_session_for_recipe(user_id, record.id)
                if self.chat_repository is not None
                else None
            )
            session_summary = None
            if latest_session is not None:
                session_summary = ChatSessionSummary(
                    session_id=latest_session.id,
                    recipe_id=latest_session.recipe_id,
                    title=latest_session.title,
                    message_count=latest_session.message_count or 0,
                    last_message_at=(
                        to_china_time(latest_session.last_message_at)
                        if latest_session.last_message_at
                        else None
                    ),
                    created_at=to_china_time(latest_session.created_at),
                )
            items.append(
                RecipeHistoryItem(
                    recipe_id=record.id,
                    recognition_id=record.recognition_id,
                    title=str(record.recipe_data.get("title", "未命名菜谱")),
                    version=record.version,
                    provider=recognition.provider,
                    model_version=recognition.model_version,
                    image_count=len(recognition.image_object_names or []),
                    confirmed_ingredients=list(recognition.confirmed_ingredients or []),
                    updated_at=to_china_time(record.updated_at),
                    latest_session=session_summary,
                )
            )
        return RecipeHistoryPage(items=items, total=total, page=page, page_size=page_size)

    async def update_recipe(
        self,
        recipe_id: int,
        user_id: int,
        new_recipe_data: dict,
        *,
        change_reason: str | None = None,
        source_message_id: int | None = None,
    ) -> RecipeResponse:
        try:
            validated = RecipeGenerateResult.model_validate(new_recipe_data)
        except ValidationError as exc:
            raise InvalidRecipeLLMOutputError() from exc
        record = self.recipe_repository.save_new_recipe_version(
            recipe_id,
            user_id,
            validated.model_dump(mode="json"),
            change_type="chat_update",
            change_reason=change_reason,
            source_message_id=source_message_id,
        )
        if record is None:
            existing = self.recipe_repository.get_recipe(recipe_id)
            if existing is None:
                raise RecipeNotFoundError()
            raise RecipePermissionDeniedError()
        return self._to_response(record)

    async def list_versions(self, recipe_id: int, user_id: int) -> RecipeVersionList:
        current = await self.get_recipe(recipe_id, user_id)
        records = self.recipe_repository.list_versions(recipe_id, user_id) or []
        return RecipeVersionList(
            recipe_id=recipe_id,
            current_version=current.version,
            versions=[
                self._to_version_summary(record, current.version, user_id) for record in records
            ],
        )

    async def get_version(
        self, recipe_id: int, version: int, user_id: int
    ) -> RecipeVersionDetail:
        current = await self.get_recipe(recipe_id, user_id)
        record = self.recipe_repository.get_version(recipe_id, version, user_id)
        if record is None:
            raise RecipeVersionNotFoundError()
        return RecipeVersionDetail(
            **self._to_version_summary(record, current.version, user_id).model_dump(),
            recipe=RecipeGenerateResult.model_validate(record.recipe_data),
        )

    async def restore_version(
        self, recipe_id: int, version: int, user_id: int
    ) -> RecipeResponse:
        await self.get_version(recipe_id, version, user_id)
        record = self.recipe_repository.restore_version(recipe_id, version, user_id)
        if record is None:
            raise RecipeVersionNotFoundError()
        return self._to_response(record)

    def _to_version_summary(
        self, record, current_version: int, user_id: int
    ) -> RecipeVersionSummary:
        source_message = None
        if self.chat_repository is not None and record.source_message_id is not None:
            message = self.chat_repository.get_message(record.source_message_id)
            session = (
                self.chat_repository.get_session_for_user(message.session_id, user_id)
                if message is not None
                else None
            )
            if session is not None and session.recipe_id == record.recipe_id:
                source_message = message.content
        return RecipeVersionSummary(
            version=record.version,
            title=str(record.recipe_data.get("title", "未命名菜谱")),
            change_type=record.change_type,
            change_reason=record.change_reason,
            source_message_id=record.source_message_id,
            source_message=source_message,
            source_version=record.source_version,
            is_current=record.version == current_version,
            created_at=to_china_time(record.created_at),
        )
