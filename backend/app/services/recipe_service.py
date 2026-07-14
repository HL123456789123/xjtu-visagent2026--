"""
菜谱服务模块 - 修正版
核心职责：从识别记录生成菜谱，支持 LLM 生成 + 降级模板

修正内容：
1. 入口改为 create_recipe_from_recognition（符合 API 契约）
2. 使用 Pydantic Schema 严格校验再入库
3. 日期字段使用 datetime.now() 而非字符串
4. nutrition 补上 disclaimer 字段
5. 统一异步风格
6. 配置读取增加容错
7. 增加超时和重试机制
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
    Ingredient,
    NutritionInfo,
    RecipeGenerateResult,
    RecipeGenerateResponse,
    RecipeResponse,
    RecipeStep,
)
from app.services.recognition_repository import RecognitionRepository  # 由绕家辉实现

logger = get_logger("recipe_service")

# 固定免责声明
NUTRITION_DISCLAIMER = "本营养数据为AI估算值，仅供参考，不构成医学建议。如需精确营养数据，请咨询专业营养师。"


class RecipeService:
    """菜谱服务类"""

    # 菜谱生成系统提示词
    SYSTEM_PROMPT = """你是一位专业的中餐厨师，拥有丰富的烹饪经验。

根据用户提供的食材，生成一份详细、实用的菜谱。

要求：
1. 菜名要简洁、有吸引力
2. 食材用量要准确、可操作
3. 步骤要详细、清晰，适合新手
4. 营养数据为估算值，仅供参考
5. 如果食材组合不合理，给出最佳搭配建议

请严格按照以下 JSON 格式返回，不要包含其他内容：
{
    "title": "菜名",
    "description": "一句话简介",
    "ingredients": [
        {"name": "食材名", "amount": 用量数字, "unit": "单位", "category": "分类"}
    ],
    "steps": [
        {"step_number": 1, "description": "详细步骤描述", "duration_minutes": 预计耗时分钟数}
    ],
    "cuisine": "chinese/western/japanese/korean/other",
    "difficulty": "easy/medium/hard",
    "prep_time_minutes": 准备时间分钟数,
    "cook_time_minutes": 烹饪时间分钟数,
    "nutrition": {
        "calories": 卡路里估算值,
        "protein": 蛋白质克数,
        "fat": 脂肪克数,
        "carbs": 碳水克数
    }
}"""

    def __init__(self):
        # 延迟初始化 LLM，避免启动时因 Key 缺失而崩溃
        self._llm = None
        self._recognition_repo = RecognitionRepository()
        self._max_retries = 2
        self._timeout_seconds = 30

    @property
    def llm(self) -> Optional[ChatOpenAI]:
        """惰性初始化 LLM 客户端"""
        if self._llm is None:
            # 检查配置是否存在
            if not settings.OPENAI_API_KEY:
                logger.warning("OPENAI_API_KEY 未配置，LLM 功能不可用")
                return None

            self._llm = ChatOpenAI(
                model=settings.OPENAI_MODEL,
                openai_api_key=settings.OPENAI_API_KEY,
                openai_api_base=settings.OPENAI_BASE_URL,
                temperature=0.7,
                timeout=self._timeout_seconds,
                max_retries=1,  # 由外部重试控制
            )
        return self._llm

    async def create_recipe_from_recognition(
        self,
        recognition_id: int,
        user_id: int,
        preferences: Optional[str] = None,
        servings: Optional[int] = None,
    ) -> RecipeResponse:
        """
        从识别记录生成菜谱（主入口，符合 API 契约）

        Args:
            recognition_id: 识别任务 ID
            user_id: 当前用户 ID
            preferences: 用户偏好（少油、清淡等）
            servings: 份数，不传则使用识别记录中的值或默认 2

        Returns:
            持久化后的菜谱响应

        Raises:
            RecipeGenerationError: 生成失败（LLM 和降级均失败）
            PermissionError: 识别记录不属于当前用户
        """
        logger.info(
            f"开始从识别记录生成菜谱: recognition_id={recognition_id}, user_id={user_id}"
        )

        # 1. 查询识别记录，获取确认后的食材
        recognition = await self._recognition_repo.get_by_id(
            recognition_id, user_id
        )
        if recognition is None:
            raise RecipeNotFoundError(f"识别记录不存在或无权访问: {recognition_id}")

        confirmed_ingredients = recognition.get("confirmed_ingredients")
        if not confirmed_ingredients:
            raise RecipeGenerationError("该识别任务尚未确认食材，无法生成菜谱")

        # 提取食材名称列表
        ingredient_names = [
            item.get("name") for item in confirmed_ingredients if item.get("name")
        ]
        if not ingredient_names:
            raise RecipeGenerationError("确认的食材列表为空")

        # 确定份数
        final_servings = servings or recognition.get("servings", 2)

        # 2. 尝试 LLM 生成
        raw_result = None
        source = "fallback"
        confidence = 0.5

        for attempt in range(self._max_retries + 1):
            try:
                raw_result = await self._generate_with_llm(
                    ingredients=ingredient_names,
                    preferences=preferences,
                    servings=final_servings,
                )
                source = "llm"
                confidence = raw_result.get("confidence", 0.85)
                break
            except Exception as e:
                logger.warning(
                    f"LLM 生成失败 (尝试 {attempt + 1}/{self._max_retries + 1}): {e}"
                )
                if attempt >= self._max_retries:
                    logger.info("所有 LLM 尝试失败，使用降级方案")
                    raw_result = self._generate_fallback(
                        ingredients=ingredient_names,
                        servings=final_servings,
                    )
                    source = "fallback"
                    confidence = 0.5

        # 3. 用 Pydantic Schema 校验
        try:
            generate_result = RecipeGenerateResult(**raw_result)
        except ValidationError as e:
            logger.error(f"AI 生成的菜谱结构校验失败: {e}")
            logger.info("使用降级方案替代")
            raw_result = self._generate_fallback(
                ingredients=ingredient_names,
                servings=final_servings,
            )
            generate_result = RecipeGenerateResult(**raw_result)
            source = "fallback"
            confidence = 0.5

        # 4. 存入数据库
        recipe = await self._save_recipe(
            recognition_id=recognition_id,
            user_id=user_id,
            result=generate_result,
            source=source,
            preferences=preferences,
        )

        # 5. 构建并返回响应
        return RecipeResponse(
            id=recipe["id"],
            recognition_id=recognition_id,
            title=recipe["title"],
            description=recipe.get("description"),
            ingredients=recipe["ingredients"],
            steps=recipe["steps"],
            nutrition=recipe.get("nutrition"),
            cuisine=recipe.get("cuisine"),
            difficulty=recipe["difficulty"],
            prep_time_minutes=recipe["prep_time_minutes"],
            cook_time_minutes=recipe["cook_time_minutes"],
            servings=recipe["servings"],
            image_url=recipe.get("image_url"),
            source=source,
            version=recipe.get("version", 1),
            user_id=user_id,
            created_at=recipe["created_at"],
            updated_at=recipe["updated_at"],
        )

    async def _generate_with_llm(
        self,
        ingredients: List[str],
        preferences: Optional[str],
        servings: int,
    ) -> Dict[str, Any]:
        """
        调用 LLM 生成菜谱（带超时控制）

        Returns:
            包含菜谱数据的字典（不含数据库字段）
        """
        llm = self.llm
        if llm is None:
            raise ValueError("LLM 客户端未初始化，请检查 OPENAI_API_KEY 配置")

        # 构建用户消息
        user_message = f"我有这些食材：{', '.join(ingredients)}\n"
        user_message += f"请帮我生成一份{servings}人份的菜谱。"
        if preferences:
            user_message += f"偏好：{preferences}"

        messages = [
            SystemMessage(content=self.SYSTEM_PROMPT),
            HumanMessage(content=user_message),
        ]

        logger.debug(f"调用 LLM，食材: {ingredients}")

        # 使用 asyncio.timeout 控制整体超时
        try:
            async with asyncio.timeout(self._timeout_seconds):
                response = await llm.ainvoke(messages)
        except asyncio.TimeoutError:
            raise TimeoutError(f"LLM 调用超时（{self._timeout_seconds}秒）")

        # 解析 JSON
        try:
            # 尝试提取 JSON（可能被 markdown 代码块包裹）
            content = response.content
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()

            data = json.loads(content)
        except (json.JSONDecodeError, IndexError) as e:
            raise ValueError(f"LLM 返回的 JSON 解析失败: {e}")

        # 确保 nutrition 包含 disclaimer
        if "nutrition" in data and data["nutrition"]:
            data["nutrition"]["disclaimer"] = NUTRITION_DISCLAIMER

        logger.info(f"LLM 生成成功: {data.get('title')}")
        return data

    def _generate_fallback(
        self,
        ingredients: List[str],
        servings: int,
    ) -> Dict[str, Any]:
        """
        降级方案：返回通用菜谱模板

        当 LLM 调用失败时使用，返回结构必须与 RecipeGenerateResult 兼容
        """
        logger.info("使用降级方案生成菜谱")

        # 根据食材数量生成更合理的默认数据
        if len(ingredients) == 1:
            title = f"清炒{ingredients[0]}"
            description = f"简单快手的清炒{ingredients[0]}"
        elif len(ingredients) <= 3:
            title = f"{''.join(ingredients)}小炒"
            description = f"用{', '.join(ingredients)}搭配的家常小炒"
        else:
            title = "什锦家常菜"
            description = f"用{', '.join(ingredients[:3])}等食材制作的什锦菜肴"

        # 构建食材列表（合理分配用量）
        ingredient_list = []
        for idx, name in enumerate(ingredients):
            if name in ["盐", "糖", "酱油", "醋", "料酒", "姜", "蒜"]:
                # 调味料
                ingredient_list.append(
                    {"name": name, "amount": 5, "unit": "克", "category": "调味料"}
                )
            elif name in ["鸡蛋", "蛋"]:
                ingredient_list.append({"name": name, "amount": 2, "unit": "个", "category": "蛋类"})
            elif name in ["番茄", "西红柿"]:
                ingredient_list.append({"name": name, "amount": 200, "unit": "克", "category": "蔬菜"})
            else:
                ingredient_list.append(
                    {"name": name, "amount": 150, "unit": "克", "category": "其他"}
                )

        return {
            "title": title,
            "description": description,
            "ingredients": ingredient_list,
            "steps": [
                RecipeStep(
                    step_number=1,
                    description="将食材洗净，切成适当大小",
                    duration_minutes=5,
                ),
                RecipeStep(
                    step_number=2,
                    description="热锅下油，油热后放入食材翻炒",
                    duration_minutes=5,
                ),
                RecipeStep(
                    step_number=3,
                    description="加入适量盐、酱油等调味料调味",
                    duration_minutes=2,
                ),
                RecipeStep(
                    step_number=4,
                    description="翻炒均匀后出锅装盘",
                    duration_minutes=1,
                ),
            ],
            "cuisine": "chinese",
            "difficulty": "easy",
            "prep_time_minutes": 5,
            "cook_time_minutes": 8,
            "servings": servings,
            "nutrition": NutritionInfo(
                calories=200.0,
                protein=10.0,
                fat=8.0,
                carbs=15.0,
                fiber=2.0,
                disclaimer=NUTRITION_DISCLAIMER,
            ).model_dump(),
        }

    async def _save_recipe(
        self,
        recognition_id: int,
        user_id: int,
        result: RecipeGenerateResult,
        source: str,
        preferences: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        保存菜谱到数据库

        这里是模拟实现，实际由 ORM 完成
        """
        logger.info(f"保存菜谱: {result.title}, user_id={user_id}")

        # 模拟入库（实际应调用 Repository）
        # 注意：这里返回的字典必须包含 id、created_at、updated_at
        return {
            "id": 1,  # 模拟 ID
            "recognition_id": recognition_id,
            "title": result.title,
            "description": result.description,
            "ingredients": [ing.model_dump() for ing in result.ingredients],
            "steps": [step.model_dump() for step in result.steps],
            "nutrition": result.nutrition.model_dump() if result.nutrition else None,
            "cuisine": result.cuisine,
            "difficulty": result.difficulty.value,
            "prep_time_minutes": result.prep_time_minutes,
            "cook_time_minutes": result.cook_time_minutes,
            "servings": result.servings,
            "image_url": None,
            "source": source,
            "version": 1,
            "user_id": user_id,
            "created_at": datetime.now(),
            "updated_at": datetime.now(),
        }


# 单例实例
recipe_service = RecipeService()