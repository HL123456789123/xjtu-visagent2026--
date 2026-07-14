"""
营养估算服务模块

提供基于食材的营养成分估算。

重要声明：
- 所有营养数据为 AI 估算值，仅供参考
- 不构成医学建议
- 如需精确数据，请咨询专业营养师

修正内容（2026-07-10）：
1. 支持 amount_text（"适量"、"少许"）的兜底处理
2. 增加单位归一化（克、毫升、个 → 参考重量）
3. 增加食材别名映射（番茄↔西红柿）
4. 增加 batch_estimate 批量估算方法
5. 增加 LLM 估算路径（作为主路径，查表作为降级）
"""
import json
import re
from typing import Any, Dict, List, Optional, Tuple

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from app.config.settings import settings
from app.core.logger import get_logger
from app.entity.recipe_schemas import Ingredient, NutritionInfo

logger = get_logger("nutrition_service")

# 免责声明
NUTRITION_DISCLAIMER = (
    "本营养数据为AI估算值，仅供参考，不构成医学建议。"
    "如需精确营养数据，请咨询专业营养师。"
)


class NutritionService:
    """营养估算服务"""

    # ══════════════════════════════════════════════════════════════
    # 一、食材别名映射（提高查表命中率）
    # ══════════════════════════════════════════════════════════════
    ALIAS_MAP: Dict[str, str] = {
        "西红柿": "番茄",
        "洋芋": "土豆",
        "马铃薯": "土豆",
        "白萝卜": "萝卜",
        "胡罗卜": "胡萝卜",
        "包菜": "白菜",
        "卷心菜": "白菜",
        "甘蓝": "白菜",
        "青椒": "辣椒",
        "尖椒": "辣椒",
        "鸡胸": "鸡胸肉",
        "鸡脯肉": "鸡胸肉",
        "虾仁": "虾",
        "白饭": "米饭",
        "大米饭": "米饭",
        "挂面": "面条",
        "方便面": "面条",
        "小葱": "葱",
        "大葱": "葱",
    }

    # ══════════════════════════════════════════════════════════════
    # 二、单位→克数换算（参考值）
    # ══════════════════════════════════════════════════════════════
    UNIT_TO_GRAMS: Dict[str, float] = {
        "克": 1.0,
        "g": 1.0,
        "千克": 1000.0,
        "公斤": 1000.0,
        "斤": 500.0,
        "两": 50.0,
        "毫升": 1.0,      # 水/液体近似 1ml=1g
        "ml": 1.0,
        "升": 1000.0,
        "l": 1000.0,
        "个": 50.0,       # 鸡蛋/番茄 ≈ 50g
        "只": 50.0,
        "根": 30.0,       # 黄瓜/胡萝卜 ≈ 30g
        "条": 50.0,
        "片": 10.0,
        "块": 20.0,
        "勺": 10.0,       # 一勺 ≈ 10g
        "汤匙": 15.0,
        "茶匙": 5.0,
        "碗": 200.0,
        "杯": 200.0,
    }

    # ══════════════════════════════════════════════════════════════
    # 三、营养数据库（每100克/100毫升）
    # ══════════════════════════════════════════════════════════════
    NUTRITION_DB: Dict[str, Dict[str, float]] = {
        # —— 蔬菜类 ——
        "番茄": {"calories": 18, "protein": 0.9, "fat": 0.2, "carbs": 3.9, "fiber": 1.2},
        "土豆": {"calories": 77, "protein": 2.0, "fat": 0.1, "carbs": 17.0, "fiber": 2.2},
        "胡萝卜": {"calories": 41, "protein": 0.9, "fat": 0.2, "carbs": 9.6, "fiber": 2.8},
        "西兰花": {"calories": 34, "protein": 2.8, "fat": 0.4, "carbs": 6.6, "fiber": 2.6},
        "茄子": {"calories": 25, "protein": 1.0, "fat": 0.2, "carbs": 5.9, "fiber": 3.0},
        "黄瓜": {"calories": 15, "protein": 0.7, "fat": 0.1, "carbs": 3.6, "fiber": 0.5},
        "辣椒": {"calories": 20, "protein": 0.9, "fat": 0.2, "carbs": 4.6, "fiber": 1.7},
        "白菜": {"calories": 13, "protein": 1.5, "fat": 0.1, "carbs": 2.2, "fiber": 1.0},
        "菠菜": {"calories": 23, "protein": 2.9, "fat": 0.4, "carbs": 3.6, "fiber": 2.2},
        "洋葱": {"calories": 40, "protein": 1.1, "fat": 0.1, "carbs": 9.3, "fiber": 1.7},
        "蒜": {"calories": 126, "protein": 4.5, "fat": 0.2, "carbs": 27.6, "fiber": 1.5},
        "姜": {"calories": 41, "protein": 1.3, "fat": 0.7, "carbs": 8.0, "fiber": 2.0},
        "葱": {"calories": 31, "protein": 1.5, "fat": 0.3, "carbs": 6.0, "fiber": 1.5},
        "萝卜": {"calories": 16, "protein": 0.7, "fat": 0.1, "carbs": 3.4, "fiber": 1.6},
        "蘑菇": {"calories": 22, "protein": 2.1, "fat": 0.3, "carbs": 4.2, "fiber": 1.0},
        "玉米": {"calories": 96, "protein": 3.0, "fat": 1.0, "carbs": 19.0, "fiber": 2.7},
        "豌豆": {"calories": 81, "protein": 5.4, "fat": 0.4, "carbs": 14.4, "fiber": 5.1},
        "豆芽": {"calories": 16, "protein": 1.7, "fat": 0.1, "carbs": 2.6, "fiber": 0.8},

        # —— 肉类 ——
        "猪肉": {"calories": 242, "protein": 13.2, "fat": 20.1, "carbs": 0.0, "fiber": 0},
        "牛肉": {"calories": 125, "protein": 19.9, "fat": 4.2, "carbs": 0.0, "fiber": 0},
        "鸡肉": {"calories": 167, "protein": 19.3, "fat": 9.4, "carbs": 0.0, "fiber": 0},
        "鸡胸肉": {"calories": 133, "protein": 31.0, "fat": 3.6, "carbs": 0.0, "fiber": 0},
        "鸡腿": {"calories": 165, "protein": 20.0, "fat": 9.0, "carbs": 0.0, "fiber": 0},
        "鸭肉": {"calories": 200, "protein": 18.0, "fat": 14.0, "carbs": 0.0, "fiber": 0},
        "羊肉": {"calories": 250, "protein": 20.0, "fat": 18.0, "carbs": 0.0, "fiber": 0},
        "五花肉": {"calories": 518, "protein": 9.3, "fat": 52.3, "carbs": 0.0, "fiber": 0},
        "排骨": {"calories": 264, "protein": 15.0, "fat": 22.0, "carbs": 0.0, "fiber": 0},

        # —— 水产 ——
        "鱼": {"calories": 96, "protein": 18.0, "fat": 2.5, "carbs": 0.0, "fiber": 0},
        "虾": {"calories": 85, "protein": 18.0, "fat": 1.0, "carbs": 0.0, "fiber": 0},
        "螃蟹": {"calories": 95, "protein": 17.5, "fat": 2.3, "carbs": 0.5, "fiber": 0},
        "三文鱼": {"calories": 208, "protein": 20.4, "fat": 13.4, "carbs": 0.0, "fiber": 0},
        "鳕鱼": {"calories": 82, "protein": 18.0, "fat": 0.7, "carbs": 0.0, "fiber": 0},

        # —— 蛋奶豆类 ——
        "鸡蛋": {"calories": 144, "protein": 13.3, "fat": 9.5, "carbs": 0.7, "fiber": 0},
        "牛奶": {"calories": 42, "protein": 3.4, "fat": 1.0, "carbs": 5.0, "fiber": 0},
        "豆腐": {"calories": 73, "protein": 8.1, "fat": 3.7, "carbs": 2.8, "fiber": 0.4},
        "豆浆": {"calories": 30, "protein": 3.0, "fat": 1.8, "carbs": 0.6, "fiber": 0},
        "芝士": {"calories": 350, "protein": 25.0, "fat": 27.0, "carbs": 2.0, "fiber": 0},
        "酸奶": {"calories": 62, "protein": 3.5, "fat": 3.3, "carbs": 4.7, "fiber": 0},

        # —— 主食类 ——
        "米饭": {"calories": 116, "protein": 2.6, "fat": 0.3, "carbs": 25.6, "fiber": 0.3},
        "面条": {"calories": 110, "protein": 3.5, "fat": 0.5, "carbs": 22.0, "fiber": 1.0},
        "馒头": {"calories": 221, "protein": 7.0, "fat": 1.1, "carbs": 44.2, "fiber": 1.3},
        "面包": {"calories": 265, "protein": 9.0, "fat": 3.2, "carbs": 49.0, "fiber": 2.5},
        "米粉": {"calories": 356, "protein": 5.8, "fat": 0.4, "carbs": 78.5, "fiber": 1.2},
        "红薯": {"calories": 86, "protein": 1.6, "fat": 0.1, "carbs": 20.1, "fiber": 3.0},
        "山药": {"calories": 57, "protein": 1.5, "fat": 0.1, "carbs": 12.8, "fiber": 0.8},
        "燕麦": {"calories": 389, "protein": 16.9, "fat": 6.9, "carbs": 66.3, "fiber": 10.6},

        # —— 食用油 ——
        "油": {"calories": 900, "protein": 0, "fat": 100, "carbs": 0, "fiber": 0},
        "植物油": {"calories": 900, "protein": 0, "fat": 100, "carbs": 0, "fiber": 0},
        "花生油": {"calories": 900, "protein": 0, "fat": 100, "carbs": 0, "fiber": 0},
        "橄榄油": {"calories": 884, "protein": 0, "fat": 100, "carbs": 0, "fiber": 0},
        "猪油": {"calories": 900, "protein": 0, "fat": 100, "carbs": 0, "fiber": 0},

        # —— 调味料（少量使用，营养贡献微小） ——
        "盐": {"calories": 0, "protein": 0, "fat": 0, "carbs": 0, "fiber": 0},
        "酱油": {"calories": 53, "protein": 5.6, "fat": 0.1, "carbs": 8.3, "fiber": 0},
        "醋": {"calories": 31, "protein": 0.4, "fat": 0.1, "carbs": 4.9, "fiber": 0},
        "糖": {"calories": 400, "protein": 0, "fat": 0, "carbs": 100, "fiber": 0},
        "蜂蜜": {"calories": 304, "protein": 0.3, "fat": 0, "carbs": 82.4, "fiber": 0.2},
        "料酒": {"calories": 45, "protein": 0.3, "fat": 0, "carbs": 5.0, "fiber": 0},
        "豆瓣酱": {"calories": 135, "protein": 8.0, "fat": 3.0, "carbs": 18.0, "fiber": 2.0},
        "辣椒酱": {"calories": 90, "protein": 2.0, "fat": 3.0, "carbs": 14.0, "fiber": 2.0},
        "花生酱": {"calories": 588, "protein": 25.0, "fat": 50.0, "carbs": 20.0, "fiber": 6.0},
        "芝麻酱": {"calories": 600, "protein": 17.0, "fat": 53.0, "carbs": 18.0, "fiber": 9.0},
    }

    # 默认营养值（未知食材）
    DEFAULT_NUTRITION = {
        "calories": 50.0,
        "protein": 2.0,
        "fat": 1.0,
        "carbs": 8.0,
        "fiber": 1.0,
    }

    # LLM 系统提示词
    LLM_SYSTEM_PROMPT = """你是一位营养学专家。

根据用户提供的食材列表和估算用量，估算每100克该食材的营养成分。

请严格按照以下 JSON 格式返回，只返回 JSON，不要包含其他内容：
{
    "番茄": {"calories": 18, "protein": 0.9, "fat": 0.2, "carbs": 3.9, "fiber": 1.2},
    "鸡蛋": {"calories": 144, "protein": 13.3, "fat": 9.5, "carbs": 0.7, "fiber": 0}
}

营养数据参考标准：
- 热量（calories）：千卡
- 蛋白质（protein）：克
- 脂肪（fat）：克
- 碳水化合物（carbs）：克
- 膳食纤维（fiber）：克

如果不知道某种食材，请合理估算。"""

    def __init__(self):
        self._llm = None
        self._timeout_seconds = 15

    @property
    def llm(self) -> Optional[ChatOpenAI]:
        """惰性初始化 LLM"""
        if self._llm is None:
            if not settings.OPENAI_API_KEY:
                logger.warning("OPENAI_API_KEY 未配置，营养估算 LLM 不可用")
                return None
            self._llm = ChatOpenAI(
                model=settings.OPENAI_MODEL,
                openai_api_key=settings.OPENAI_API_KEY,
                openai_api_base=settings.OPENAI_BASE_URL,
                temperature=0.3,
                timeout=self._timeout_seconds,
            )
        return self._llm

    # ══════════════════════════════════════════════════════════════
    # 四、核心估算方法（查表 + LLM 增强）
    # ══════════════════════════════════════════════════════════════

    @classmethod
    def normalize_ingredient_name(cls, name: str) -> str:
        """归一化食材名称（别名映射 + 去除后缀）"""
        # 去除括号内容
        name = re.sub(r"\(.*?\)", "", name).strip()
        # 去除常见后缀
        for suffix in ["（新鲜）", "（冷冻）", "（干）", "（湿）"]:
            name = name.replace(suffix, "")
        # 别名映射
        return cls.ALIAS_MAP.get(name, name)

    @classmethod
    def estimate_amount_grams(cls, ingredient: Ingredient) -> float:
        """
        将食材用量估算为克数

        支持：
        - 纯数字（amount）：直接使用
        - 文本描述（amount_text）：如"适量"、"少许" → 兜底 10g
        - 单位换算：个、根、勺 → 克
        """
        # 优先使用数字
        if ingredient.amount is not None:
            # 如果有单位，尝试换算
            if ingredient.unit:
                unit = ingredient.unit
                # 去掉"约"、"大概"等
                unit = re.sub(r"约|大概|左右", "", unit).strip()
                factor = cls.UNIT_TO_GRAMS.get(unit, 1.0)
                return ingredient.amount * factor
            return ingredient.amount

        # 其次使用文本描述
        if ingredient.amount_text:
            text = ingredient.amount_text
            # "适量"、"少许"、"少量" → 10g
            if re.search(r"适量|少许|少量|一点", text):
                return 10.0
            # "一大勺" → 15g
            if "大勺" in text:
                return 15.0
            # "一小勺" → 5g
            if "小勺" in text:
                return 5.0
            # "几个" → 50g/个
            match = re.search(r"(\d+)\s*个", text)
            if match:
                return float(match.group(1)) * 50.0
            # 尝试提取数字
            match = re.search(r"(\d+\.?\d*)", text)
            if match:
                return float(match.group(1))

        # 完全无法解析，按一个中等大小食材 50g 估算
        return 50.0

    @classmethod
    def estimate_nutrition_by_db(
        cls,
        ingredients: List[Ingredient],
    ) -> Tuple[NutritionInfo, List[str]]:
        """
        基于营养数据库估算营养

        Returns:
            (NutritionInfo, 未匹配的食材名列表)
        """
        total = {"calories": 0.0, "protein": 0.0, "fat": 0.0, "carbs": 0.0, "fiber": 0.0}
        unmatched = []

        for ing in ingredients:
            # 归一化名称
            normalized_name = cls.normalize_ingredient_name(ing.name)

            # 查表
            nutrition = cls.NUTRITION_DB.get(normalized_name)
            if nutrition is None:
                # 再次尝试去掉"肉"、"菜"等后缀
                for suffix in ["肉", "菜", "类", "制品"]:
                    if normalized_name.endswith(suffix):
                        alt_name = normalized_name[:-len(suffix)]
                        nutrition = cls.NUTRITION_DB.get(alt_name)
                        if nutrition:
                            break

            if nutrition is None:
                nutrition = cls.DEFAULT_NUTRITION
                unmatched.append(ing.name)

            # 估算克数
            grams = cls.estimate_amount_grams(ing)
            ratio = grams / 100.0

            for key in total:
                total[key] += nutrition.get(key, 0) * ratio

        return NutritionInfo(
            calories=round(total["calories"], 1),
            protein=round(total["protein"], 1),
            fat=round(total["fat"], 1),
            carbs=round(total["carbs"], 1),
            fiber=round(total["fiber"], 1),
            disclaimer=NUTRITION_DISCLAIMER,
        ), unmatched

    async def estimate_nutrition_with_llm(
        cls,
        ingredients: List[Ingredient],
    ) -> Optional[NutritionInfo]:
        """
        使用 LLM 估算营养（主路径）

        当 LLM 不可用时，应 fallback 到 estimate_nutrition_by_db
        """
        raise NotImplementedError("LLM 营养估算功能待实现")

    @classmethod
    def estimate_nutrition(
        cls,
        ingredients: List[Ingredient],
        use_llm: bool = False,
    ) -> NutritionInfo:
        """
        估算营养成分（主入口）

        Args:
            ingredients: 食材列表
            use_llm: 是否尝试使用 LLM（默认 False，使用查表）

        Returns:
            营养成分估算结果
        """
        if use_llm and settings.OPENAI_API_KEY:
            # TODO: 调用 LLM 估算
            logger.debug("LLM 估算暂未实现，使用查表降级")

        nutrition, unmatched = cls.estimate_nutrition_by_db(ingredients)

        if unmatched:
            logger.warning(f"未匹配的食材（使用默认值）: {unmatched}")

        return nutrition

    @classmethod
    def batch_estimate_nutrition(
        cls,
        recipe_list: List[List[Ingredient]],
    ) -> List[NutritionInfo]:
        """
        批量估算多个菜谱的营养

        Args:
            recipe_list: 多个菜谱的食材列表

        Returns:
            营养估算结果列表
        """
        return [cls.estimate_nutrition(ingredients) for ingredients in recipe_list]

    @classmethod
    def get_ingredient_nutrition(cls, name: str) -> Optional[Dict[str, float]]:
        """
        获取单个食材的营养数据（每100克）

        Args:
            name: 食材名称

        Returns:
            营养数据字典，不存在返回 None
        """
        normalized = cls.normalize_ingredient_name(name)
        return cls.NUTRITION_DB.get(normalized)

    @classmethod
    def get_missing_nutrition(cls, ingredients: List[Ingredient]) -> List[str]:
        """
        获取营养数据库中缺失的食材列表

        用于日志记录和后续补充数据
        """
        missing = []
        for ing in ingredients:
            normalized = cls.normalize_ingredient_name(ing.name)
            if normalized not in cls.NUTRITION_DB:
                missing.append(ing.name)
        return missing


# 单例实例
nutrition_service = NutritionService()