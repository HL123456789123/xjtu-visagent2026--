import json
import re
from datetime import datetime
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures"


def load_fixture(name: str) -> dict:
    with (FIXTURE_DIR / name).open(encoding="utf-8") as file:
        return json.load(file)


def assert_iso_8601_with_timezone(value: str) -> None:
    parsed = datetime.fromisoformat(value)
    assert parsed.tzinfo is not None, f"{value} must include timezone offset"


def assert_api_response_envelope(payload: dict, code: int, message: str) -> None:
    assert set(payload) == {"code", "message", "data"}
    assert payload["code"] == code
    assert payload["message"] == message
    assert isinstance(payload["data"], dict)


def assert_bbox(payload: dict) -> None:
    assert set(payload) == {"x1", "y1", "x2", "y2"}
    assert all(isinstance(payload[key], (int, float)) for key in payload)


def assert_ingredient_candidate(payload: dict) -> None:
    assert set(payload) == {
        "candidate_id",
        "class_name",
        "display_name",
        "confidence",
        "bbox",
        "source",
    }
    assert payload["candidate_id"].startswith("det-")
    assert isinstance(payload["class_name"], str) and payload["class_name"]
    assert isinstance(payload["display_name"], str) and payload["display_name"]
    assert 0 <= payload["confidence"] <= 1
    assert_bbox(payload["bbox"])
    assert payload["source"] in {"model", "manual"}


def assert_food_recognition_payload(payload: dict, expected_provider: str) -> None:
    assert_api_response_envelope(payload, 201, "识别完成")
    data = payload["data"]
    assert set(data) == {
        "recognition_id",
        "status",
        "provider",
        "model_version",
        "image_url",
        "ingredients",
        "created_at",
    }
    assert type(data["recognition_id"]) is int
    assert data["status"] == "completed"
    assert data["provider"] == expected_provider
    assert data["provider"] in {"mock", "yolo"}
    assert data["image_url"] == f"/api/files/food/{data['recognition_id']}"
    assert isinstance(data["ingredients"], list)
    assert_iso_8601_with_timezone(data["created_at"])
    for ingredient in data["ingredients"]:
        assert_ingredient_candidate(ingredient)


def read_backend_file(relative_path: str) -> str:
    path = BACKEND_DIR / relative_path
    assert path.exists(), f"V1 requires backend/{relative_path}, but it is missing"
    return path.read_text(encoding="utf-8")


def assert_regex(text: str, pattern: str, message: str) -> None:
    assert re.search(pattern, text, flags=re.MULTILINE | re.DOTALL), message


def test_food_recognition_success_fixture_matches_v1_contract():
    assert_food_recognition_payload(load_fixture("food_recognition_success.json"), "yolo")


def test_food_recognition_empty_fixture_matches_v1_contract():
    assert_food_recognition_payload(load_fixture("food_recognition_empty.json"), "mock")


def test_v1_food_api_exposes_three_required_routes():
    source = read_backend_file("app/api/food.py")

    assert 'APIRouter(prefix="/api/food"' in source or "APIRouter(prefix='/api/food'" in source
    assert_regex(
        source,
        r"@router\.post\(\s*['\"]/?recognitions['\"]",
        "Food API must expose POST /api/food/recognitions",
    )
    assert_regex(
        source,
        r"@router\.get\(\s*['\"]/?recognitions/\{recognition_id\}['\"]",
        "Food API must expose GET /api/food/recognitions/{recognition_id}",
    )
    assert_regex(
        source,
        r"@router\.put\(\s*['\"]/?recognitions/\{recognition_id\}/ingredients['\"]",
        "Food API must expose PUT /api/food/recognitions/{recognition_id}/ingredients",
    )


def test_v1_food_api_requires_login_and_current_user_isolation():
    source = read_backend_file("app/api/food.py")

    assert "get_current_user" in source
    assert "current_user" in source
    assert not re.search(
        r"def\s+\w+\([^)]*user_id\s*:",
        source,
        flags=re.DOTALL,
    ), "client must not upload user_id to Food API route parameters"
    assert (
        "get_recognition_for_user" in source
        or "current_user.id" in source
        or ".user_id" in source
    ), "Food API must scope recognition reads/writes to current_user"


def test_v1_food_router_is_registered_in_main():
    source = read_backend_file("main.py")

    assert "food" in source.lower(), "backend/main.py must import and include the V1 food router"
