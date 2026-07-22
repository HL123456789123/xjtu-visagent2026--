import copy
import json
import re
from datetime import datetime
from pathlib import Path

import pytest


BACKEND_DIR = Path(__file__).resolve().parents[1]
FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures"
FOOD_RECOGNITION_CREATED_MESSAGE = "识别完成"
MB = 1024 * 1024
MAX_IMAGES_PER_BATCH = 5
MAX_SINGLE_IMAGE_BYTES = 10 * MB
MAX_IMAGE_BATCH_BYTES = 50 * MB


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


def assert_food_image(payload: dict, recognition_id: int, expected_index: int) -> None:
    assert set(payload) == {"image_index", "image_url"}
    assert type(payload["image_index"]) is int
    assert payload["image_index"] == expected_index
    assert payload["image_url"] == f"/api/files/food/{recognition_id}/{expected_index}"


def assert_ingredient_candidate(payload: dict, image_indexes: set[int]) -> None:
    assert set(payload) == {
        "candidate_id",
        "image_index",
        "class_name",
        "display_name",
        "confidence",
        "bbox",
        "source",
    }
    assert type(payload["image_index"]) is int
    assert payload["image_index"] in image_indexes
    assert payload["candidate_id"].startswith(f"img-{payload['image_index']}-det-")
    assert isinstance(payload["class_name"], str) and payload["class_name"]
    assert isinstance(payload["display_name"], str) and payload["display_name"]
    assert 0 <= payload["confidence"] <= 1
    assert_bbox(payload["bbox"])
    assert payload["source"] in {"model", "manual"}


def assert_food_recognition_payload(payload: dict, expected_provider: str) -> None:
    assert_api_response_envelope(payload, 201, FOOD_RECOGNITION_CREATED_MESSAGE)
    data = payload["data"]
    assert set(data) == {
        "recognition_id",
        "status",
        "provider",
        "model_version",
        "images",
        "ingredients",
        "created_at",
    }
    assert type(data["recognition_id"]) is int
    assert data["status"] == "completed"
    assert data["provider"] == expected_provider
    assert data["provider"] in {"mock", "yolo"}
    assert "image_url" not in data
    assert isinstance(data["images"], list)
    assert 1 <= len(data["images"]) <= MAX_IMAGES_PER_BATCH
    image_indexes = set(range(len(data["images"])))
    for expected_index, image in enumerate(data["images"]):
        assert_food_image(image, data["recognition_id"], expected_index)
    assert isinstance(data["ingredients"], list)
    assert_iso_8601_with_timezone(data["created_at"])
    for ingredient in data["ingredients"]:
        assert_ingredient_candidate(ingredient, image_indexes)


def assert_valid_image_count(image_count: int) -> None:
    if image_count < 1 or image_count > MAX_IMAGES_PER_BATCH:
        raise ValueError("INVALID_IMAGE_COUNT")


def assert_valid_single_image_size(size_bytes: int) -> None:
    if size_bytes > MAX_SINGLE_IMAGE_BYTES:
        raise ValueError("IMAGE_TOO_LARGE")


def assert_valid_batch_total_size(image_sizes: list[int]) -> None:
    if any(size > MAX_SINGLE_IMAGE_BYTES for size in image_sizes):
        raise ValueError("IMAGE_TOO_LARGE")
    if sum(image_sizes) > MAX_IMAGE_BATCH_BYTES:
        raise ValueError("IMAGE_BATCH_TOO_LARGE")


def assert_ingredients_reference_images(payload: dict) -> None:
    data = payload["data"]
    image_indexes = {image["image_index"] for image in data["images"]}
    for ingredient in data["ingredients"]:
        assert "image_index" in ingredient
        assert type(ingredient["image_index"]) is int
        assert ingredient["image_index"] in image_indexes


def build_atomic_food_batch(per_image_results: list[dict]) -> dict:
    if any("error" in result for result in per_image_results):
        raise RuntimeError("FOOD_BATCH_FAILED")

    ingredients = []
    for image_index, result in enumerate(per_image_results):
        for detection_index, detection in enumerate(result.get("detections", []), start=1):
            ingredients.append(
                {
                    "candidate_id": f"img-{image_index}-det-{detection_index}",
                    "image_index": image_index,
                    **detection,
                }
            )
    return {"status": "completed", "ingredients": ingredients}


def read_backend_file(relative_path: str) -> str:
    path = BACKEND_DIR / relative_path
    assert path.exists(), f"V1 requires backend/{relative_path}, but it is missing"
    return path.read_text(encoding="utf-8")


def assert_regex(text: str, pattern: str, message: str) -> None:
    assert re.search(pattern, text, flags=re.MULTILINE | re.DOTALL), message


def test_food_recognition_success_fixture_matches_v1_1_contract():
    assert_food_recognition_payload(load_fixture("food_recognition_success.json"), "yolo")


def test_food_recognition_empty_fixture_matches_v1_1_contract():
    payload = load_fixture("food_recognition_empty.json")
    assert_food_recognition_payload(payload, "mock")
    assert payload["data"]["ingredients"] == []


@pytest.mark.parametrize("image_count", [1, 5])
def test_v1_1_food_image_count_accepts_contract_boundaries(image_count: int):
    assert_valid_image_count(image_count)


@pytest.mark.parametrize("image_count", [0, 6])
def test_v1_1_food_image_count_rejects_out_of_range_batches(image_count: int):
    with pytest.raises(ValueError, match="INVALID_IMAGE_COUNT"):
        assert_valid_image_count(image_count)


def test_v1_1_food_single_image_size_accepts_10_mb():
    assert_valid_single_image_size(MAX_SINGLE_IMAGE_BYTES)


def test_v1_1_food_single_image_size_rejects_more_than_10_mb():
    with pytest.raises(ValueError, match="IMAGE_TOO_LARGE"):
        assert_valid_single_image_size(MAX_SINGLE_IMAGE_BYTES + 1)


def test_v1_1_food_batch_total_size_accepts_50_mb():
    assert_valid_batch_total_size([MAX_SINGLE_IMAGE_BYTES] * MAX_IMAGES_PER_BATCH)


def test_v1_1_food_batch_total_size_rejects_more_than_50_mb():
    with pytest.raises(ValueError, match="IMAGE_BATCH_TOO_LARGE"):
        # This defensive-size test bypasses the public image-count rule. A valid
        # request has at most five 10 MiB files and therefore cannot exceed 50 MiB.
        assert_valid_batch_total_size([MAX_SINGLE_IMAGE_BYTES] * MAX_IMAGES_PER_BATCH + [1])


def test_v1_1_food_single_image_error_has_priority_over_batch_error():
    with pytest.raises(ValueError, match="IMAGE_TOO_LARGE"):
        assert_valid_batch_total_size([MAX_SINGLE_IMAGE_BYTES + 1] * MAX_IMAGES_PER_BATCH)


def test_v1_1_food_ingredients_reference_input_images_by_index():
    assert_ingredients_reference_images(load_fixture("food_recognition_success.json"))


@pytest.mark.parametrize(
    "bad_index",
    [
        pytest.param(None, id="missing"),
        pytest.param(-1, id="negative"),
        pytest.param(2, id="out-of-range"),
        pytest.param("0", id="non-integer"),
    ],
)
def test_v1_1_food_ingredients_reject_invalid_or_unmatched_image_index(bad_index):
    payload = copy.deepcopy(load_fixture("food_recognition_success.json"))
    ingredient = payload["data"]["ingredients"][0]
    if bad_index is None:
        ingredient.pop("image_index")
    else:
        ingredient["image_index"] = bad_index

    with pytest.raises(AssertionError):
        assert_ingredients_reference_images(payload)


def test_v1_1_food_batch_failure_is_atomic_and_returns_no_partial_success():
    with pytest.raises(RuntimeError, match="FOOD_BATCH_FAILED"):
        build_atomic_food_batch(
            [
                {
                    "detections": [
                        {
                            "class_name": "tomato",
                            "display_name": "Tomato",
                            "confidence": 0.93,
                            "bbox": {"x1": 1, "y1": 2, "x2": 3, "y2": 4},
                            "source": "model",
                        }
                    ]
                },
                {"error": "provider failed"},
            ]
        )


def test_v1_1_food_canonical_fixtures_do_not_keep_legacy_single_image_standard():
    assert sorted(path.name for path in FIXTURE_DIR.glob("food_recognition*.json")) == [
        "food_recognition_empty.json",
        "food_recognition_success.json",
    ]
    for fixture_name in ["food_recognition_empty.json", "food_recognition_success.json"]:
        data = load_fixture(fixture_name)["data"]
        assert "images" in data
        assert "image_url" not in data


def test_v1_1_food_api_exposes_three_required_routes():
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


def test_v1_1_food_api_requires_login_and_current_user_isolation():
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


def test_v1_1_food_api_uses_images_field_without_public_single_image_alias():
    source = read_backend_file("app/api/food.py")

    assert "images" in source
    assert "image:" not in source
    assert "image =" not in source
    assert "partial_success" not in source


def test_v1_1_food_router_is_registered_in_main():
    source = read_backend_file("main.py")

    assert "food" in source.lower(), "backend/main.py must import and include the V1.1 food router"
