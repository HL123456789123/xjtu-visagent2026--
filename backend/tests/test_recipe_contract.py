import json
import re
from datetime import datetime
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures"
NUTRITION_DISCLAIMER = "营养数据由模型估算，仅供参考，不构成医疗或营养建议。"


def load_fixture(name: str) -> dict:
    with (FIXTURE_DIR / name).open(encoding="utf-8") as file:
        return json.load(file)


def assert_iso_8601_with_timezone(value: str) -> None:
    parsed = datetime.fromisoformat(value)
    assert parsed.tzinfo is not None, f"{value} must include timezone offset"


def assert_recipe_payload(payload: dict) -> None:
    assert set(payload) == {"code", "message", "data"}
    assert payload["code"] == 201
    assert payload["message"] == "菜谱生成成功"

    data = payload["data"]
    assert set(data) == {
        "recipe_id",
        "recognition_id",
        "version",
        "title",
        "summary",
        "servings",
        "cooking_time_minutes",
        "difficulty",
        "ingredients",
        "steps",
        "nutrition",
        "nutrition_disclaimer",
        "generator",
        "created_at",
        "updated_at",
    }
    assert type(data["recipe_id"]) is int
    assert type(data["recognition_id"]) is int
    assert type(data["version"]) is int
    assert data["version"] == 1
    assert isinstance(data["title"], str) and data["title"]
    assert isinstance(data["summary"], str) and data["summary"]
    assert type(data["servings"]) is int and data["servings"] >= 1
    assert type(data["cooking_time_minutes"]) is int
    assert isinstance(data["difficulty"], str) and data["difficulty"]
    assert data["nutrition_disclaimer"] == NUTRITION_DISCLAIMER
    assert_iso_8601_with_timezone(data["created_at"])
    assert_iso_8601_with_timezone(data["updated_at"])

    for ingredient in data["ingredients"]:
        assert set(ingredient) == {"name", "amount", "unit", "note"}
        assert isinstance(ingredient["name"], str) and ingredient["name"]
        assert isinstance(ingredient["amount"], (int, float))
        assert isinstance(ingredient["unit"], str) and ingredient["unit"]

    for index, step in enumerate(data["steps"], start=1):
        assert set(step) == {"step_no", "description", "duration_minutes"}
        assert type(step["step_no"]) is int
        assert step["step_no"] == index
        assert isinstance(step["description"], str) and step["description"]
        assert type(step["duration_minutes"]) is int

    assert set(data["nutrition"]) == {
        "basis",
        "calories_kcal",
        "protein_g",
        "fat_g",
        "carbohydrates_g",
    }
    assert data["nutrition"]["basis"] == "per_serving"
    assert set(data["generator"]) == {"provider", "model", "is_mock"}
    assert isinstance(data["generator"]["is_mock"], bool)


def read_backend_file(relative_path: str) -> str:
    path = BACKEND_DIR / relative_path
    assert path.exists(), f"V1 requires backend/{relative_path}, but it is missing"
    return path.read_text(encoding="utf-8")


def assert_regex(text: str, pattern: str, message: str) -> None:
    assert re.search(pattern, text, flags=re.MULTILINE | re.DOTALL), message


def test_recipe_success_fixture_matches_v1_contract():
    assert_recipe_payload(load_fixture("recipe_success.json"))


def test_v1_recipe_api_exposes_generate_and_get_routes():
    source = read_backend_file("app/api/recipes.py")

    assert 'APIRouter(prefix="/api/recipes"' in source or "APIRouter(prefix='/api/recipes'" in source
    assert_regex(
        source,
        r"@router\.post\(\s*['\"]/?['\"]",
        "Recipe API must expose POST /api/recipes",
    )
    assert_regex(
        source,
        r"@router\.get\(\s*['\"]/?\{recipe_id\}['\"]",
        "Recipe API must expose GET /api/recipes/{recipe_id}",
    )


def test_v1_recipe_api_request_and_error_contract():
    source = read_backend_file("app/api/recipes.py")
    schemas = read_backend_file("app/entity/schemas.py")

    assert "recognition_id" in source + schemas
    assert "preferences" in source + schemas
    assert "servings" in source + schemas
    assert "taste" in source + schemas
    assert "NO_CONFIRMED_INGREDIENTS" in source or "未确认" in source
    assert "菜谱生成成功" in source


def test_v1_recipe_api_requires_login_and_user_isolation():
    source = read_backend_file("app/api/recipes.py")

    assert "get_current_user" in source
    assert "current_user" in source
    assert (
        "get_recipe_for_user" in source
        or "get_recognition_for_user" in source
        or "current_user.id" in source
    ), "Recipe API must scope recognition and recipe access to current_user"


def test_v1_recipe_router_is_registered_in_main():
    source = read_backend_file("main.py")

    assert "recipes" in source.lower(), "backend/main.py must import and include the V1 recipes router"
