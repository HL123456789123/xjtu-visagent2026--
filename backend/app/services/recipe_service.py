"""
菜谱服务模块（V1 执行版）

核心职责：
1. 从识别记录加载确认食材
2. 调用 LLM 生成菜谱（或使用 Mock）
3. 校验并保存菜谱

V1 规范：第六节、第七节
"""
import asyncio
import json
from datetime import datetime
from typing import Any, Dict, List, Optional

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from pydantic import ValidationError

from app.config.settings import settings
from app.core.exceptions import RecipeGenerationError, RecipeNotFoundError
from app.core.logger import get_logger
from app.entity.recipe_schemas import (
    GeneratorInfo,
    Ingredient,
    NutritionInfo,
    RecipeCreateRequest,
    RecipeGenerateResult,
    RecipePreferences,
    RecipeResponse,
    RecipeStep,
)
from app.services.agent_prompts import (
    RECIPE_GENERATION_SYSTEM_PROMPT,
    build_generation_user_prompt,
    NUTRITION_DISCLAIMER,
)
from app.services.agent_graph import generate_recipe_graph

logger = get_logger("recipe_service")


class RecipeService:
    """菜谱服务（V1 执行版）"""

    def __init__(self):
        self._llm = None
        self._max_retries = 2
        self._timeout_seconds = 60  # V1 默认 60 秒

    @property
    def llm(self) -> Optional[ChatOpenAI]:
        """惰性初始化 LLM"""
        if self._llm is None:
            if not settings.OPENAI_API_KEY:
                logger.warning("OPENAI_API_KEY 未配置，LLM 不可用")
                return None
            self._llm = ChatOpenAI(
                model=settings.OPENAI_MODEL,
                openai_api_key=settings.OPENAI_API_KEY,
                openai_api_base=settings.OPENAI_BASE_URL,
                temperature=0.7,
                timeout=self._timeout_seconds,
                max_retries=1,
            )
        return self._llm

    async def create_recipe_from_recognition(
        self,
        request: RecipeCreateRequest,
        user_id: int,
    ) -> RecipeResponse:
        """
        V1 第六节第1点：生成菜谱

        流程：
        1. 加载确认食材
        2. 调用 LLM 生成（或降级）
        3. 校验并保存
        """
        logger.info(
            f"生成菜谱: recognition_id={request.recognition_id}, user_id={user_id}"
        )

        # 1. 加载确认食材（Day3 对接 Repository）
        # 这里暂时用 Mock，Day3 替换为 Repository 调用
        confirmed_ingredients = [
            {"name": "番茄", "class_name": "tomato", "quantity": 2, "unit": "个", "source": "model"},
            {"name": "鸡蛋", "class_name": None, "quantity": 3, "unit": "个", "source": "manual"},
        ]
        if not confirmed_ingredients:
            raise RecipeGenerationError("该识别任务尚未确认食材")

        # 2. 尝试 LLM 生成
        raw_result = None
        source = "llm"
        is_mock = False

        for attempt in range(self._max_retries + 1):
            try:
                raw_result = await self._generate_with_llm(
                    confirmed_ingredients=confirmed_ingredients,
                    preferences=request.preferences,
                )
                break
            except Exception as e:
                logger.warning(f"LLM 生成失败 (尝试 {attempt+1}/{self._max_retries+1}): {e}")
                if attempt >= self._max_retries:
                    logger.info("使用降级方案")
                    raw_result = self._generate_fallback(
                        confirmed_ingredients=confirmed_ingredients,
                        preferences=request.preferences,
                    )
                    source = "fallback"
                    is_mock = True

        # 3. 校验
        try:
            generate_result = RecipeGenerateResult(**raw_result)
        except ValidationError as e:
            logger.error(f"校验失败: {e}")
            logger.info("使用降级方案替代")
            raw_result = self._generate_fallback(
                confirmed_ingredients=confirmed_ingredients,
                preferences=request.preferences,
            )
            generate_result = RecipeGenerateResult(**raw_result)
            source = "fallback"
            is_mock = True

        # 4. 保存（Day3 对接 RecipeRepository）
        # 临时 Mock 保存
        recipe_id = 1  # Mock ID
        now = datetime.now()
        generator = GeneratorInfo(
            provider="fake" if is_mock else "openai_compatible",
            model="fixture-v1" if is_mock else settings.OPENAI_MODEL,
            is_mock=is_mock,
        )

        response = RecipeResponse(
            recipe_id=recipe_id,
            recognition_id=request.recognition_id,
            version=1,
            title=generate_result.title,
            summary=generate_result.summary,
            servings=generate_result.servings,
            cooking_time_minutes=generate_result.cooking_time_minutes,
            difficulty=generate_result.difficulty,
            ingredients=generate_result.ingredients,
            steps=generate_result.steps,
            nutrition=generate_result.nutrition,
            nutrition_disclaimer=NUTRITION_DISCLAIMER,
            generator=generator,
            created_at=now,
            updated_at=now,
        )
        return response

    async def _generate_with_llm(
        self,
        confirmed_ingredients: List[Dict[str, Any]],
        preferences: RecipePreferences,
    ) -> Dict[str, Any]:
        """调用 LLM 生成菜谱"""
        llm = self.llm
        if llm is None:
            raise ValueError("LLM 未初始化")

        # 构建 Prompt（V1 第七节第2点）
        user_prompt = build_generation_user_prompt(
            confirmed_ingredients=confirmed_ingredients,
            preferences=preferences.model_dump(),
        )

        messages = [
            SystemMessage(content=RECIPE_GENERATION_SYSTEM_PROMPT),
            HumanMessage(content=user_prompt),
        ]

        try:
            async with asyncio.timeout(self._timeout_seconds):
                response = await llm.ainvoke(messages)
        except asyncio.TimeoutError:
            raise TimeoutError(f"LLM 超时 ({self._timeout_seconds}s)")

        # 解析 JSON
        content = response.content
        # 去除 Markdown 代码块
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()

        try:
            data = json.loads(content)
        except json.JSONDecodeError as e:
            raise ValueError(f"JSON 解析失败: {e}")

        # 确保 nutrition 结构完整
        if "nutrition" not in data:
            data["nutrition"] = {
                "basis": "per_serving",
                "calories_kcal": 0,
                "protein_g": 0,
                "fat_g": 0,
                "carbohydrates_g": 0,
            }
        elif "basis" not in data["nutrition"]:
            data["nutrition"]["basis"] = "per_serving"

        return data

    def _generate_fallback(
        self,
        confirmed_ingredients: List[Dict[str, Any]],
        preferences: RecipePreferences,
    ) -> Dict[str, Any]:
        """降级方案（V1 兼容）"""
        logger.info("使用降级方案生成菜谱")

        # 提取食材名称
        names = [item.get("name") for item in confirmed_ingredients if item.get("name")]
        if not names:
            names = ["食材"]

        # 构造基础菜谱
        if len(names) == 1:
            title = f"清炒{names[0]}"
        else:
            title = f"{''.join(names[:2])}小炒"

        # 构建食材列表（V1 格式）
        ingredients = [
            {"name": name, "amount": 100, "unit": "克", "note": None}
            for name in names
        ]

        steps = [
            {"step_no": 1, "description": "将所有食材洗净，切成适当大小。", "duration_minutes": 5},
            {"step_no": 2, "description": "热锅下油，油热后放入食材翻炒。", "duration_minutes": 5},
            {"step_no": 3, "description": "加入盐、酱油等调味料调味。", "duration_minutes": 2},
            {"step_no": 4, "description": "翻炒均匀后出锅装盘。", "duration_minutes": 1},
        ]

        nutrition = {
            "basis": "per_serving",
            "calories_kcal": 200,
            "protein_g": 8,
            "fat_g": 10,
            "carbohydrates_g": 15,
        }

        return {
            "title": title,
            "summary": f"用{', '.join(names)}制作的简单家常菜。",
            "servings": preferences.servings,
            "cooking_time_minutes": 20,
            "difficulty": "简单",
            "ingredients": ingredients,
            "steps": steps,
            "nutrition": nutrition,
        }

    # ========== 查询接口（V1 第六节第2点） ==========

    async def get_recipe(self, recipe_id: int, user_id: int) -> RecipeResponse:
        """查询菜谱（Day3 对接 Repository）"""
        # Mock 实现
        now = datetime.now()
        return RecipeResponse(
            recipe_id=recipe_id,
            recognition_id=1,
            version=1,
            title="番茄炒蛋",
            summary="经典家常菜",
            servings=2,
            cooking_time_minutes=20,
            difficulty="简单",
            ingredients=[{"name": "番茄", "amount": 2, "unit": "个", "note": None}],
            steps=[{"step_no": 1, "description": "番茄切块", "duration_minutes": 5}],
            nutrition=NutritionInfo(
                basis="per_serving",
                calories_kcal=280,
                protein_g=16.5,
                fat_g=15.2,
                carbohydrates_g=18.4,
            ),
            nutrition_disclaimer=NUTRITION_DISCLAIMER,
            generator=GeneratorInfo(provider="mock", model="fixture", is_mock=True),
            created_at=now,
            updated_at=now,
        )

    # ========== 更新接口（Agent 调用） ==========

    async def update_recipe(
        self,
        recipe_id: int,
        user_id: int,
        new_recipe_data: Dict[str, Any],
    ) -> RecipeResponse:
        """更新菜谱版本（Day3 对接 Repository）"""
        # 读取当前版本，增加 version
        # Mock 实现
        now = datetime.now()
        return RecipeResponse(
            recipe_id=recipe_id,
            recognition_id=1,
            version=2,  # 版本+1
            title=new_recipe_data.get("title", "番茄炒蛋"),
            summary=new_recipe_data.get("summary", "更新后的菜谱"),
            servings=new_recipe_data.get("servings", 2),
            cooking_time_minutes=new_recipe_data.get("cooking_time_minutes", 20),
            difficulty=new_recipe_data.get("difficulty", "简单"),
            ingredients=new_recipe_data.get("ingredients", []),
            steps=new_recipe_data.get("steps", []),
            nutrition=new_recipe_data.get("nutrition", NutritionInfo(
                basis="per_serving",
                calories_kcal=0,
                protein_g=0,
                fat_g=0,
                carbohydrates_g=0,
            )),
            nutrition_disclaimer=NUTRITION_DISCLAIMER,
            generator=GeneratorInfo(provider="mock", model="fixture", is_mock=True),
            created_at=now,
            updated_at=now,
        )


# 单例
recipe_service = RecipeService()