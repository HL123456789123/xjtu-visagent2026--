"""
菜谱服务模块（V1 冻结版本）
负责人：陈煜君

职责：
1. 调用 Agent Graph 生成菜谱
2. Pydantic 校验
3. 返回 RecipeResponse
"""
from datetime import datetime
from typing import Optional

from app.core.exceptions import RecipeNotFoundError, PermissionDeniedError, RecipeGenerationError
from app.core.logger import get_logger
from app.entity.recipe_schema import (
    RecipeCreateRequest,
    RecipeResponse,
    RecipeGenerateResult,
    GeneratorInfo,
    RecipePreferences,
)
from app.services.agent_graph import generate_recipe_graph
from app.services.agent_prompts import NUTRITION_DISCLAIMER

logger = get_logger("recipe_service")


class RecipeService:
    """菜谱服务类"""

    # Mock 存储（Day3 对接 Repository 后替换）
    _recipes: dict = {}
    _next_id = 1

    async def create_recipe(
        self,
        request: RecipeCreateRequest,
        user_id: int,
    ) -> RecipeResponse:
        """
        生成菜谱（V1 第六节第1点）

        Args:
            request: 创建请求（recognition_id + preferences）
            user_id: 当前用户 ID

        Returns:
            RecipeResponse

        Raises:
            RecipeGenerationError: 生成失败（含错误码）
        """
        logger.info(f"生成菜谱: recognition_id={request.recognition_id}, user_id={user_id}")

        try:
            # 调用 Agent Graph
            result = await generate_recipe_graph.ainvoke({
                "recognition_id": request.recognition_id,
                "user_id": user_id,
                "preferences": request.preferences.model_dump(),
                "confirmed_ingredients": [],
                "raw_recipe": {},
                "recipe_response": {},
            })
        except Exception as e:
            # 根据异常类型映射错误码
            error_msg = str(e)
            if "未确认食材" in error_msg:
                raise RecipeGenerationError(
                    "该识别任务尚未确认食材",
                    code="NO_CONFIRMED_INGREDIENTS"
                )
            elif "校验失败" in error_msg or "ValidationError" in error_msg:
                raise RecipeGenerationError(
                    "LLM 输出格式不合格",
                    code="INVALID_LLM_OUTPUT"
                )
            else:
                raise RecipeGenerationError(
                    "LLM 服务暂时不可用",
                    code="LLM_UNAVAILABLE"
                )

        recipe_data = result["recipe_response"]

        # 补充 Generator 信息（V1 第六节第1点）
        # Day4 改为真实 provider/model
        generator = GeneratorInfo(
            provider="fake",
            model="fixture-v1",
            is_mock=True,
        )

        # 保存到 Mock 存储
        recipe_id = self._next_id
        self._next_id += 1

        recipe = {
            "recipe_id": recipe_id,
            "recognition_id": request.recognition_id,
            "version": 1,
            "title": recipe_data.get("title"),
            "summary": recipe_data.get("summary"),
            "servings": recipe_data.get("servings", 2),
            "cooking_time_minutes": recipe_data.get("cooking_time_minutes", 0),
            "difficulty": recipe_data.get("difficulty", "简单"),
            "ingredients": recipe_data.get("ingredients", []),
            "steps": recipe_data.get("steps", []),
            "nutrition": recipe_data.get("nutrition"),
            "nutrition_disclaimer": NUTRITION_DISCLAIMER,
            "generator": generator.model_dump(),
            "user_id": user_id,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
        }

        self._recipes[recipe_id] = recipe
        logger.info(f"菜谱创建成功: recipe_id={recipe_id}")

        return RecipeResponse(**recipe)

    async def get_recipe(
        self,
        recipe_id: int,
        user_id: int,
    ) -> RecipeResponse:
        """
        查询菜谱（V1 第六节第2点）

        Args:
            recipe_id: 菜谱 ID
            user_id: 当前用户 ID

        Returns:
            RecipeResponse

        Raises:
            RecipeNotFoundError: 菜谱不存在（404）
            PermissionDeniedError: 无权访问（403）
        """
        logger.info(f"查询菜谱: recipe_id={recipe_id}, user_id={user_id}")

        recipe = self._recipes.get(recipe_id)
        if recipe is None:
            raise RecipeNotFoundError(f"菜谱不存在: {recipe_id}")

        if recipe.get("user_id") != user_id:
            raise PermissionDeniedError(f"无权访问菜谱: {recipe_id}")

        return RecipeResponse(**recipe)

    # Day3 对接：更新菜谱（Agent 调用）
    async def update_recipe(
        self,
        recipe_id: int,
        user_id: int,
        new_recipe_data: dict,
    ) -> RecipeResponse:
        """
        更新菜谱版本（V1 第六节第3点）

        Args:
            recipe_id: 菜谱 ID
            user_id: 当前用户 ID
            new_recipe_data: 新菜谱数据

        Returns:
            RecipeResponse（version + 1）
        """
        # 先获取当前菜谱
        current = await self.get_recipe(recipe_id, user_id)

        # 更新数据，版本 + 1
        updated = current.model_dump()
        updated.update(new_recipe_data)
        updated["version"] = current.version + 1
        updated["updated_at"] = datetime.now().isoformat()

        self._recipes[recipe_id] = updated
        logger.info(f"菜谱更新成功: recipe_id={recipe_id}, version={updated['version']}")

        return RecipeResponse(**updated)


# 全局实例
recipe_service = RecipeService()