"""菜谱业务服务：Repository、最小 LangGraph、结构校验与版本管理。"""

from app.core.exceptions import PermissionDeniedError, RecipeGenerationError, RecipeNotFoundError
from app.entity.recipe_schema import RecipeCreateRequest, RecipeGenerateResult, RecipeResponse
from app.services.agent_graph import generate_recipe_graph
from app.services.agent_prompts import NUTRITION_DISCLAIMER
from app.services.llm_gateway import InvalidLLMOutputError, LLMUnavailableError, get_llm_gateway
from app.repositories.recipe_repository import RecipeRepository


class RecipeService:
    def __init__(self, repository: RecipeRepository):
        self.repository = repository

    @staticmethod
    def _to_response(record) -> RecipeResponse:
        return RecipeResponse(
            recipe_id=record.id,
            recognition_id=record.recognition_id,
            version=record.version,
            **record.recipe_data,
            nutrition_disclaimer=NUTRITION_DISCLAIMER,
            generator=record.generator,
            created_at=record.created_at,
            updated_at=record.updated_at,
        )

    async def create_recipe(
        self, request: RecipeCreateRequest, user_id: int
    ) -> RecipeResponse:
        recognition = self.repository.get_recognition_for_user(
            request.recognition_id, user_id
        )
        if recognition is None:
            raise RecipeGenerationError(
                "识别记录不存在", code="RECOGNITION_NOT_FOUND"
            )
        ingredients = self.repository.get_confirmed_ingredients(
            request.recognition_id, user_id
        )
        if not ingredients:
            raise RecipeGenerationError(
                "该识别任务尚未确认食材", code="NO_CONFIRMED_INGREDIENTS"
            )
        try:
            result = await generate_recipe_graph.ainvoke(
                {
                    "confirmed_ingredients": ingredients,
                    "preferences": request.preferences.model_dump(),
                    "raw_recipe": None,
                }
            )
            recipe_data = RecipeGenerateResult.model_validate(result["raw_recipe"])
            gateway = get_llm_gateway()
        except InvalidLLMOutputError as exc:
            raise RecipeGenerationError(
                "LLM 输出格式不合格", code="INVALID_LLM_OUTPUT"
            ) from exc
        except LLMUnavailableError as exc:
            raise RecipeGenerationError(
                "智能服务暂时不可用", code="LLM_UNAVAILABLE"
            ) from exc

        record = self.repository.create_recipe(
            user_id,
            request.recognition_id,
            recipe_data.model_dump(mode="json"),
            gateway.generator,
        )
        return self._to_response(record)

    async def get_recipe(self, recipe_id: int, user_id: int) -> RecipeResponse:
        record = self.repository.get_recipe(recipe_id)
        if record is None:
            raise RecipeNotFoundError("菜谱不存在")
        if record.user_id != user_id:
            raise PermissionDeniedError("无权访问该菜谱")
        return self._to_response(record)

    async def update_recipe(
        self, recipe_id: int, user_id: int, new_recipe_data: dict
    ) -> RecipeResponse:
        validated = RecipeGenerateResult.model_validate(new_recipe_data)
        record = self.repository.save_new_recipe_version(
            recipe_id, user_id, validated.model_dump(mode="json")
        )
        if record is None:
            if self.repository.get_recipe(recipe_id) is None:
                raise RecipeNotFoundError("菜谱不存在")
            raise PermissionDeniedError("无权修改该菜谱")
        return self._to_response(record)
