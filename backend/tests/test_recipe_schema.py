import pytest
from pydantic import ValidationError

from app.entity.recipe_schema import (
    ChatLLMResult,
    CreateChatSessionRequest,
    Ingredient,
    RecipeCreateRequest,
    RecipeGenerateResult,
    SendChatMessageRequest,
)


def recipe_payload():
    return {
        "title": "番茄炒蛋",
        "summary": "家常快手菜",
        "servings": 2,
        "cooking_time_minutes": 20,
        "difficulty": "简单",
        "ingredients": [{"name": "番茄", "amount": 2, "unit": "个", "note": None}],
        "steps": [{"step_no": 1, "description": "洗净切块", "duration_minutes": 5}],
        "nutrition": {
            "basis": "per_serving", "calories_kcal": 280, "protein_g": 16.5,
            "fat_g": 15.2, "carbohydrates_g": 18.4,
        },
    }


def test_recipe_contract_accepts_canonical_payload():
    assert RecipeGenerateResult.model_validate(recipe_payload()).title == "番茄炒蛋"
    assert RecipeCreateRequest(recognition_id=12).preferences.servings == 2


def test_empty_ingredient_name_is_rejected():
    with pytest.raises(ValidationError):
        Ingredient(name="", amount=1, unit="个")


def test_chat_action_must_match_recipe():
    with pytest.raises(ValidationError):
        ChatLLMResult(action="update_recipe", answer="已修改", recipe=None)


def test_chat_requests_only_accept_v1_fields():
    CreateChatSessionRequest(recipe_id=1)
    SendChatMessageRequest(content="少放油")
    with pytest.raises(ValidationError):
        SendChatMessageRequest(content="少放油", message="旧字段")
