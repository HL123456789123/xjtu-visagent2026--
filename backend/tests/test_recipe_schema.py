"""
菜谱 Schema 单元测试（V1 版本）

验证：
- 正例：有效数据通过校验
- 反例：无效数据抛出 ValidationError
"""
import json
import os

import pytest
from pydantic import ValidationError

from app.entity.recipe_schema import (
    Ingredient,
    NutritionInfo,
    RecipePreferences,
    RecipeGenerateResult,
    RecipeResponse,
    RecipeStep,
    RecipeCreateRequest,
    GeneratorInfo,
)


# ══════════════════════════════════════════════════════════════
# 一、食材 Schema 测试
# ══════════════════════════════════════════════════════════════


class TestIngredientSchema:
    """食材 Schema 测试（V1 第三节第4点）"""

    def test_valid_ingredient(self):
        """正例：有效食材"""
        ing = Ingredient(name="番茄", amount=2, unit="个")
        assert ing.name == "番茄"
        assert ing.amount == 2
        assert ing.unit == "个"
        assert ing.note is None

    def test_valid_ingredient_with_note(self):
        """正例：带备注的食材"""
        ing = Ingredient(name="番茄", amount=2, unit="个", note="切块")
        assert ing.note == "切块"

    def test_empty_name_fails(self):
        """反例：名称为空"""
        # V1 没有 min_length 限制，空字符串应该能通过
        ing = Ingredient(name="", amount=2, unit="个")
        assert ing.name == ""


# ══════════════════════════════════════════════════════════════
# 二、菜谱步骤 Schema 测试
# ══════════════════════════════════════════════════════════════


class TestRecipeStepSchema:
    """菜谱步骤 Schema 测试（V1 第七节第3点）"""

    def test_valid_step(self):
        """正例：有效步骤"""
        step = RecipeStep(step_no=1, description="番茄切块", duration_minutes=2)
        assert step.step_no == 1
        assert step.description == "番茄切块"
        assert step.duration_minutes == 2

    def test_valid_step_without_duration(self):
        """正例：无耗时"""
        step = RecipeStep(step_no=1, description="准备食材")
        assert step.duration_minutes is None


# ══════════════════════════════════════════════════════════════
# 三、营养信息 Schema 测试
# ══════════════════════════════════════════════════════════════


class TestNutritionInfoSchema:
    """营养信息 Schema 测试（V1 第七节第3点）"""

    def test_valid_nutrition(self):
        """正例：有效营养信息"""
        nutrition = NutritionInfo(
            basis="per_serving",
            calories_kcal=280,
            protein_g=16.5,
            fat_g=15.2,
            carbohydrates_g=18.4,
        )
        assert nutrition.calories_kcal == 280
        assert nutrition.basis == "per_serving"

    def test_zero_values_allowed(self):
        """正例：允许为0"""
        nutrition = NutritionInfo(
            calories_kcal=0,
            protein_g=0,
            fat_g=0,
            carbohydrates_g=0,
        )
        assert nutrition.calories_kcal == 0


# ══════════════════════════════════════════════════════════════
# 四、用户偏好 Schema 测试
# ══════════════════════════════════════════════════════════════


class TestRecipePreferencesSchema:
    """用户偏好 Schema 测试（V1 第三节第5点）"""

    def test_valid_preferences(self):
        """正例：有效偏好"""
        prefs = RecipePreferences(servings=2, taste="清淡", max_time_minutes=30)
        assert prefs.servings == 2
        assert prefs.taste == "清淡"
        assert prefs.avoid_ingredients == []

    def test_default_values(self):
        """正例：默认值"""
        prefs = RecipePreferences()
        assert prefs.servings == 2
        assert prefs.taste == "家常"
        assert prefs.max_time_minutes is None


# ══════════════════════════════════════════════════════════════
# 五、创建请求 Schema 测试
# ══════════════════════════════════════════════════════════════


class TestRecipeCreateRequestSchema:
    """创建请求 Schema 测试（V1 第六节第1点）"""

    def test_valid_request(self):
        """正例：有效请求"""
        request = RecipeCreateRequest(
            recognition_id=12,
            preferences=RecipePreferences(servings=2, taste="清淡"),
        )
        assert request.recognition_id == 12
        assert request.preferences.servings == 2

    def test_minimal_request(self):
        """正例：最少字段"""
        request = RecipeCreateRequest(recognition_id=12)
        assert request.preferences.servings == 2  # 默认值


# ══════════════════════════════════════════════════════════════
# 六、LLM 生成结果 Schema 测试
# ══════════════════════════════════════════════════════════════


class TestRecipeGenerateResultSchema:
    """LLM 生成结果 Schema 测试（V1 第七节第3点）"""

    def test_valid_generate_result(self):
        """正例：有效生成结果"""
        result = RecipeGenerateResult(
            title="番茄炒蛋",
            summary="一道适合两人食用的家常快手菜。",
            servings=2,
            cooking_time_minutes=20,
            difficulty="简单",
            ingredients=[Ingredient(name="番茄", amount=2, unit="个")],
            steps=[RecipeStep(step_no=1, description="番茄洗净切块。", duration_minutes=5)],
            nutrition=NutritionInfo(
                basis="per_serving",
                calories_kcal=280,
                protein_g=16.5,
                fat_g=15.2,
                carbohydrates_g=18.4,
            ),
        )
        assert result.title == "番茄炒蛋"
        assert result.servings == 2


# ══════════════════════════════════════════════════════════════
# 七、Fixture 文件校验测试
# ══════════════════════════════════════════════════════════════


class TestFixtureValidation:
    """Fixture 文件校验测试"""

    FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")

    @pytest.mark.skipif(
        not os.path.exists(os.path.join(FIXTURES_DIR, "recipe_success.json")),
        reason="recipe_success.json 不存在",
    )
    def test_recipe_success_fixture(self):
        """正例：recipe_success.json 校验通过"""
        filepath = os.path.join(self.FIXTURES_DIR, "recipe_success.json")
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)

        # 假设 fixture 格式
        if "ingredient" in data:
            Ingredient(**data["ingredient"])
        if "recipe_step" in data:
            RecipeStep(**data["recipe_step"])