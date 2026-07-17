"""Recipe orchestration through the shared V1 repositories and minimal graph."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from pydantic import ValidationError

from app.core.exceptions import AppException
from app.entity.recipe_schemas import RecipeCreateRequest, RecipeGenerateResult, RecipeResponse
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
    ) -> None:
        self.food_repository = food_repository
        self.recipe_repository = recipe_repository

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

    async def update_recipe(
        self, recipe_id: int, user_id: int, new_recipe_data: dict
    ) -> RecipeResponse:
        try:
            validated = RecipeGenerateResult.model_validate(new_recipe_data)
        except ValidationError as exc:
            raise InvalidRecipeLLMOutputError() from exc
        record = self.recipe_repository.save_new_recipe_version(
            recipe_id, user_id, validated.model_dump(mode="json")
        )
        if record is None:
            existing = self.recipe_repository.get_recipe(recipe_id)
            if existing is None:
                raise RecipeNotFoundError()
            raise RecipePermissionDeniedError()
        return self._to_response(record)
