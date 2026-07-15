import json
from datetime import datetime
from pathlib import Path


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


def test_food_recognition_success_fixture_matches_v1_contract():
    assert_food_recognition_payload(load_fixture("food_recognition_success.json"), "yolo")


def test_food_recognition_empty_fixture_matches_v1_contract():
    assert_food_recognition_payload(load_fixture("food_recognition_empty.json"), "mock")
