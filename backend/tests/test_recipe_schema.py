"""
菜谱 Schema 单元测试

验证：
- 正例：有效数据通过校验
- 反例：无效数据抛出 ValidationError
"""
import json
import os

import pytest
from pydantic import ValidationError

from app.entity.recipe_schemas import (
    DifficultyLevel,
    Ingredient,
    NutritionInfo,
    RecipeCreate,
    RecipeGenerateRequest,
    RecipeGenerateResult,
    RecipeGenerateResponse,
    RecipeListResponse,
    RecipeResponse,
    RecipeStep,
    RecipeUpdateRequest,
)


# ══════════════════════════════════════════════════════════════
# 一、食材 Schema 测试
# ══════════════════════════════════════════════════════════════


class TestIngredientSchema:
    """食材 Schema 测试"""

    def test_valid_ingredient_with_amount(self):
        """正例：有效食材（数字用量）"""
        ing = Ingredient(name="番茄", amount=2, unit="个", category="蔬菜")
        assert ing.name == "番茄"
        assert ing.amount == 2
        assert ing.unit == "个"
        assert ing.category == "蔬菜"

    def test_valid_ingredient_with_amount_text(self):
        """正例：有效食材（文本用量）"""
        ing = Ingredient(name="盐", amount_text="适量", unit="克")
        assert ing.name == "盐"
        assert ing.amount is None
        assert ing.amount_text == "适量"

    def test_valid_ingredient_minimal(self):
        """正例：最少字段"""
        ing = Ingredient(name="鸡蛋", amount=3, unit="个")
        assert ing.category is None

    def test_empty_name_fails(self):
        """反例：名称为空"""
        with pytest.raises(ValidationError):
            Ingredient(name="", amount=2, unit="个")

    def test_negative_amount_fails(self):
        """反例：数量为负"""
        with pytest.raises(ValidationError):
            Ingredient(name="番茄", amount=-1, unit="个")

    def test_zero_amount_fails(self):
        """反例：数量为0"""
        with pytest.raises(ValidationError):
            Ingredient(name="番茄", amount=0, unit="个")

    def test_missing_both_amount_and_amount_text_fails(self):
        """反例：amount 和 amount_text 都为空"""
        with pytest.raises(ValidationError):
            Ingredient(name="番茄", unit="个")


# ══════════════════════════════════════════════════════════════
# 二、菜谱步骤 Schema 测试
# ══════════════════════════════════════════════════════════════


class TestRecipeStepSchema:
    """菜谱步骤 Schema 测试"""

    def test_valid_step(self):
        """正例：有效步骤"""
        step = RecipeStep(step_number=1, description="番茄切块", duration_minutes=2)
        assert step.step_number == 1
        assert step.description == "番茄切块"
        assert step.duration_minutes == 2

    def test_valid_step_without_duration(self):
        """正例：无耗时"""
        step = RecipeStep(step_number=1, description="准备食材")
        assert step.duration_minutes is None

    def test_zero_step_number_fails(self):
        """反例：步骤号为0"""
        with pytest.raises(ValidationError):
            RecipeStep(step_number=0, description="测试")

    def test_negative_step_number_fails(self):
        """反例：步骤号为负"""
        with pytest.raises(ValidationError):
            RecipeStep(step_number=-1, description="测试")

    def test_empty_description_fails(self):
        """反例：描述为空"""
        with pytest.raises(ValidationError):
            RecipeStep(step_number=1, description="")

    def test_description_too_long_fails(self):
        """反例：描述超过500字"""
        with pytest.raises(ValidationError):
            RecipeStep(step_number=1, description="a" * 501)


# ══════════════════════════════════════════════════════════════
# 三、营养信息 Schema 测试
# ══════════════════════════════════════════════════════════════


class TestNutritionInfoSchema:
    """营养信息 Schema 测试"""

    def test_valid_nutrition(self):
        """正例：有效营养信息"""
        nutrition = NutritionInfo(
            calories=100,
            protein=10,
            fat=5,
            carbs=15,
            disclaimer="仅供参考",
        )
        assert nutrition.calories == 100
        assert nutrition.disclaimer == "仅供参考"

    def test_negative_calories_fails(self):
        """反例：卡路里为负"""
        with pytest.raises(ValidationError):
            NutritionInfo(
                calories=-1,
                protein=10,
                fat=5,
                carbs=15,
                disclaimer="test",
            )

    def test_zero_values_allowed(self):
        """正例：允许为0"""
        nutrition = NutritionInfo(
            calories=0,
            protein=0,
            fat=0,
            carbs=0,
            disclaimer="test",
        )
        assert nutrition.calories == 0


# ══════════════════════════════════════════════════════════════
# 四、菜谱创建请求 Schema 测试（修正版）
# ══════════════════════════════════════════════════════════════


class TestRecipeCreateSchema:
    """菜谱创建请求 Schema 测试（只收 recognition_id）"""

    def test_valid_recipe_create(self):
        """正例：有效请求"""
        request = RecipeCreate(
            recognition_id=123,
            preferences="少油，清淡",
            servings=2,
        )
        assert request.recognition_id == 123
        assert request.preferences == "少油，清淡"
        assert request.servings == 2

    def test_valid_recipe_create_minimal(self):
        """正例：最少字段"""
        request = RecipeCreate(recognition_id=123)
        assert request.preferences is None
        assert request.servings is None

    def test_negative_recognition_id_fails(self):
        """反例：recognition_id 为负"""
        with pytest.raises(ValidationError):
            RecipeCreate(recognition_id=-1)

    def test_negative_servings_fails(self):
        """反例：份数为负"""
        with pytest.raises(ValidationError):
            RecipeCreate(recognition_id=123, servings=-1)

    def test_servings_too_large_fails(self):
        """反例：份数超过20"""
        with pytest.raises(ValidationError):
            RecipeCreate(recognition_id=123, servings=100)


# ══════════════════════════════════════════════════════════════
# 五、菜谱生成结果 Schema 测试（新增）
# ══════════════════════════════════════════════════════════════


class TestRecipeGenerateResultSchema:
    """AI 生成结果 Schema 测试"""

    def test_valid_generate_result(self):
        """正例：有效生成结果"""
        result = RecipeGenerateResult(
            title="番茄炒蛋",
            ingredients=[Ingredient(name="番茄", amount=2, unit="个")],
            steps=[RecipeStep(step_number=1, description="切块")],
            difficulty=DifficultyLevel.EASY,
            servings=2,
        )
        assert result.title == "番茄炒蛋"
        assert result.servings == 2

    def test_step_order_validation(self):
        """正例：步骤序号连续"""
        result = RecipeGenerateResult(
            title="测试",
            ingredients=[Ingredient(name="番茄", amount=2, unit="个")],
            steps=[
                RecipeStep(step_number=1, description="步骤1"),
                RecipeStep(step_number=2, description="步骤2"),
                RecipeStep(step_number=3, description="步骤3"),
            ],
            servings=2,
        )
        assert len(result.steps) == 3

    def test_step_order_non_continuous_fails(self):
        """反例：步骤序号不连续"""
        with pytest.raises(ValidationError):
            RecipeGenerateResult(
                title="测试",
                ingredients=[Ingredient(name="番茄", amount=2, unit="个")],
                steps=[
                    RecipeStep(step_number=1, description="步骤1"),
                    RecipeStep(step_number=3, description="步骤3"),  # 跳过2
                ],
                servings=2,
            )


# ══════════════════════════════════════════════════════════════
# 六、菜谱更新请求 Schema 测试（新增）
# ══════════════════════════════════════════════════════════════


class TestRecipeUpdateRequestSchema:
    """菜谱更新请求 Schema 测试"""

    def test_valid_update_title_only(self):
        """正例：只更新标题"""
        request = RecipeUpdateRequest(title="新菜名")
        assert request.title == "新菜名"
        assert request.ingredients is None

    def test_valid_update_full(self):
        """正例：更新多个字段"""
        request = RecipeUpdateRequest(
            title="新菜名",
            ingredients=[Ingredient(name="番茄", amount=3, unit="个")],
            servings=4,
        )
        assert request.title == "新菜名"
        assert len(request.ingredients) == 1
        assert request.servings == 4

    def test_empty_request_is_valid(self):
        """正例：空更新请求（什么都不改）"""
        request = RecipeUpdateRequest()
        assert request.model_dump(exclude_none=True) == {}


# ══════════════════════════════════════════════════════════════
# 七、枚举类型测试
# ══════════════════════════════════════════════════════════════


class TestEnumTypes:
    """枚举类型测试"""

    def test_difficulty_level_values(self):
        """测试难度等级枚举值"""
        assert DifficultyLevel.EASY.value == "easy"
        assert DifficultyLevel.MEDIUM.value == "medium"
        assert DifficultyLevel.HARD.value == "hard"


# ══════════════════════════════════════════════════════════════
# 八、Fixture 文件校验测试
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

    @pytest.mark.skipif(
        not os.path.exists(os.path.join(FIXTURES_DIR, "recipe_failure.json")),
        reason="recipe_failure.json 不存在",
    )
    def test_recipe_failure_fixture(self):
        """反例：recipe_failure.json 校验失败"""
        filepath = os.path.join(self.FIXTURES_DIR, "recipe_failure.json")
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)

        # 测试每个反例
        for case_name, case_data in data.items():
            if "Ingredient" in case_name:
                with pytest.raises(ValidationError):
                    Ingredient(**case_data)
            elif "RecipeStep" in case_name:
                with pytest.raises(ValidationError):
                    RecipeStep(**case_data)