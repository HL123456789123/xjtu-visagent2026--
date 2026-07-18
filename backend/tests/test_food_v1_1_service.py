from __future__ import annotations

from datetime import datetime
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import FastAPI, UploadFile
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.food import file_router, get_food_recognition_service, router
from app.core.exceptions import AppException, app_exception_handler
from app.core.security import get_current_user
from app.database.session import Base
from app.entity.db_models import User
from app.entity.food_schemas import ConfirmedIngredient, FoodRecognitionCreateData
from app.modeling.food_yolo_runtime import BoundingBox, FoodModelUnavailableError, ModelDetection
from app.repositories.chat_repository import ChatRepository
from app.repositories.food_repository import FoodRepository
from app.repositories.recipe_repository import RecipeRepository
from app.services.food_recognition_service import (
    FoodRecognitionService,
    ImageBatchTooLargeError,
    ImageTooLargeError,
    InvalidImageContentError,
    InvalidImageCountError,
    UnsupportedImageTypeError,
)


def image_bytes(image_format: str = "PNG") -> bytes:
    output = BytesIO()
    Image.new("RGB", (2, 2), color=(255, 0, 0)).save(output, format=image_format)
    return output.getvalue()


def make_upload(name: str, content: bytes, content_type: str) -> UploadFile:
    return UploadFile(
        filename=name,
        file=BytesIO(content),
        headers={"content-type": content_type},
    )


class FakeRepository:
    def __init__(self) -> None:
        self.tasks: dict[int, SimpleNamespace] = {}
        self.next_id = 1

    def create_recognition(self, **values):
        task = SimpleNamespace(
            id=self.next_id,
            raw_detections=[],
            confirmed_ingredients=[],
            updated_at=values["created_at"],
            **values,
        )
        self.tasks[task.id] = task
        self.next_id += 1
        return task

    def get_recognition(self, recognition_id: int):
        return self.tasks.get(recognition_id)

    def save_raw_detections(self, recognition_id: int, detections_by_image):
        task = self.tasks.get(recognition_id)
        if task is not None:
            task.raw_detections = detections_by_image
        return task

    def replace_confirmed_ingredients(
        self, recognition_id: int, user_id: int, ingredients, confirmed_at: datetime
    ):
        task = self.tasks.get(recognition_id)
        if task is None or task.user_id != user_id:
            return None
        task.confirmed_ingredients = ingredients
        task.updated_at = confirmed_at
        return task

    def delete_recognition(self, recognition_id: int) -> None:
        self.tasks.pop(recognition_id, None)


class FakeStorage:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}
        self.deleted: list[str] = []

    def upload_file(self, object_name: str, file_path: str) -> str:
        self.objects[object_name] = Path(file_path).read_bytes()
        return object_name

    def delete_file(self, object_name: str) -> None:
        self.deleted.append(object_name)
        self.objects.pop(object_name, None)

    def get_file(self, object_name: str) -> bytes:
        return self.objects[object_name]


class RecordingProvider:
    def __init__(self, *, fail_on_call: int | None = None) -> None:
        self.fail_on_call = fail_on_call
        self.paths: list[str] = []

    def recognize(self, image_path: str, conf_threshold: float = 0.25):
        self.paths.append(image_path)
        if self.fail_on_call == len(self.paths):
            raise FoodModelUnavailableError("test provider failed")
        return [
            ModelDetection(
                class_name="tomato",
                confidence=max(conf_threshold, 0.9),
                bbox=BoundingBox(x1=1, y1=2, x2=30, y2=40),
            )
        ]


def make_service(*, provider: RecordingProvider | None = None):
    repository = FakeRepository()
    storage = FakeStorage()
    provider = provider or RecordingProvider()
    service = FoodRecognitionService(
        repository=repository,
        provider=provider,
        object_storage=storage,
        provider_name="yolo",
        model_version="food-yolo-v1",
        display_names={"tomato": "番茄"},
    )
    return service, repository, storage, provider


def make_food_api(service: FoodRecognitionService) -> FastAPI:
    app = FastAPI()
    app.add_exception_handler(AppException, app_exception_handler)
    app.include_router(router)
    app.include_router(file_router)
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=1)
    app.dependency_overrides[get_food_recognition_service] = lambda: service
    return app


@pytest.mark.asyncio
async def test_multi_image_service_keeps_order_and_assigns_image_index():
    service, repository, storage, provider = make_service()
    result = await service.create_recognition(
        user_id=7,
        images=[
            make_upload("first.jpg", image_bytes("JPEG"), "image/jpeg"),
            make_upload("second.png", image_bytes("PNG"), "image/png"),
        ],
        conf_threshold=0.25,
    )

    assert result.recognition_id == 1
    assert [image.model_dump() for image in result.images] == [
        {"image_index": 0, "image_url": "/api/files/food/1/0"},
        {"image_index": 1, "image_url": "/api/files/food/1/1"},
    ]
    assert [item.candidate_id for item in result.ingredients] == [
        "img-0-det-1",
        "img-1-det-1",
    ]
    assert [item.image_index for item in result.ingredients] == [0, 1]
    assert "image_url" not in result.model_dump(exclude={"images"})
    assert all(Path(path).is_absolute() for path in provider.paths)
    task = repository.tasks[1]
    assert [group["image_index"] for group in task.raw_detections] == [0, 1]
    assert len(storage.objects) == 2

    second_content, media_type = await service.get_image(
        user_id=7, recognition_id=1, image_index=1
    )
    assert second_content == image_bytes("PNG")
    assert media_type == "image/png"


@pytest.mark.parametrize("count", [1, 5])
def test_image_count_accepts_v1_1_boundaries(count: int):
    FoodRecognitionService._validate_image_count(count)


@pytest.mark.parametrize("count", [0, 6])
def test_image_count_rejects_outside_v1_1_boundaries(count: int):
    with pytest.raises(InvalidImageCountError) as exc_info:
        FoodRecognitionService._validate_image_count(count)
    assert exc_info.value.error_code == "INVALID_IMAGE_COUNT"


def test_size_boundaries_distinguish_single_and_batch_errors():
    FoodRecognitionService._validate_batch_sizes(
        [FoodRecognitionService.MAX_SINGLE_IMAGE_BYTES] * 5
    )
    with pytest.raises(ImageTooLargeError) as single_error:
        FoodRecognitionService._validate_batch_sizes(
            [FoodRecognitionService.MAX_SINGLE_IMAGE_BYTES + 1]
        )
    assert single_error.value.error_code == "IMAGE_TOO_LARGE"

    # The defensive batch guard remains useful even though the public 1..5 and
    # 10 MiB rules make this combination unreachable through a valid request.
    with pytest.raises(ImageBatchTooLargeError) as batch_error:
        FoodRecognitionService._validate_batch_sizes(
            [FoodRecognitionService.MAX_SINGLE_IMAGE_BYTES] * 5 + [1]
        )
    assert batch_error.value.error_code == "IMAGE_BATCH_TOO_LARGE"


@pytest.mark.asyncio
async def test_invalid_type_and_invalid_content_use_different_v1_errors():
    service, _, _, _ = make_service()
    with pytest.raises(UnsupportedImageTypeError):
        await service.create_recognition(
            user_id=1,
            images=[make_upload("food.gif", b"GIF89a", "image/gif")],
            conf_threshold=0.25,
        )
    with pytest.raises(InvalidImageContentError):
        await service.create_recognition(
            user_id=1,
            images=[make_upload("food.jpg", b"not-an-image", "image/jpeg")],
            conf_threshold=0.25,
        )


@pytest.mark.asyncio
async def test_provider_failure_is_atomic_for_storage_and_repository():
    service, repository, storage, _ = make_service(
        provider=RecordingProvider(fail_on_call=2)
    )
    with pytest.raises(Exception) as exc_info:
        await service.create_recognition(
            user_id=1,
            images=[
                make_upload("first.jpg", image_bytes("JPEG"), "image/jpeg"),
                make_upload("second.png", image_bytes("PNG"), "image/png"),
            ],
            conf_threshold=0.25,
        )

    assert getattr(exc_info.value, "error_code", None) == "FOOD_MODEL_UNAVAILABLE"
    assert repository.tasks == {}
    assert storage.objects == {}
    assert len(storage.deleted) == 2


@pytest.mark.asyncio
async def test_confirm_replaces_snapshot_without_implicit_deduplication():
    service, _, _, _ = make_service()
    created = await service.create_recognition(
        user_id=1,
        images=[make_upload("food.png", image_bytes("PNG"), "image/png")],
        conf_threshold=0.25,
    )
    confirmation = service.confirm_ingredients(
        user_id=1,
        recognition_id=created.recognition_id,
        ingredients=[
            ConfirmedIngredient(
                name="番茄", class_name="tomato", quantity=1, unit="个", source="model"
            ),
            ConfirmedIngredient(
                name="番茄", class_name="tomato", quantity=2, unit="个", source="model"
            ),
        ],
    )
    assert [item.quantity for item in confirmation.confirmed_ingredients] == [1, 2]


def test_canonical_food_fixtures_validate_against_public_schema():
    fixtures = Path(__file__).parent / "fixtures"
    import json

    for name in ["food_recognition_success.json", "food_recognition_empty.json"]:
        payload = json.loads((fixtures / name).read_text(encoding="utf-8"))
        parsed = FoodRecognitionCreateData.model_validate(payload["data"])
        assert 1 <= len(parsed.images) <= 5


def test_v1_1_orm_and_repositories_share_one_database_model():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    try:
        user = User(username="repository_user", email="repository@example.com", hashed_password="x")
        session.add(user)
        session.commit()
        session.refresh(user)

        food_repository = FoodRepository(session)
        recognition = food_repository.create_recognition(
            user_id=user.id,
            image_object_names=["food/one.png", "food/two.png"],
            status="completed",
            provider="mock",
            model_version="food-mock-v1",
            created_at=datetime.now().astimezone(),
        )
        food_repository.save_raw_detections(
            recognition.id,
            [
                {"image_index": 0, "image_object_name": "food/one.png", "detections": []},
                {"image_index": 1, "image_object_name": "food/two.png", "detections": []},
            ],
        )

        recipe_repository = RecipeRepository(session)
        recipe = recipe_repository.create_recipe(
            user.id,
            recognition.id,
            {"title": "测试菜谱"},
            {"provider": "fake", "model": "fixture-v1", "is_mock": True},
        )
        chat_repository = ChatRepository(session)
        chat_session = chat_repository.create_session(user.id, recipe.id)
        message = chat_repository.save_message(chat_session.id, "user", "少放盐")

        assert food_repository.get_recognition_for_user(recognition.id, user.id) is not None
        assert recipe_repository.get_recipe_for_user(recipe.id, user.id) is not None
        assert chat_repository.get_session_for_user(chat_session.id, user.id) is not None
        assert message.session_id == chat_session.id
    finally:
        session.close()
        engine.dispose()


def test_api_accepts_only_repeated_images_field():
    service, _, _, _ = make_service()
    app = make_food_api(service)

    with TestClient(app) as client:
        response = client.post(
            "/api/food/recognitions",
            files=[
                ("images", ("first.jpg", image_bytes("JPEG"), "image/jpeg")),
                ("images", ("second.png", image_bytes("PNG"), "image/png")),
            ],
        )
        legacy = client.post(
            "/api/food/recognitions",
            files={"image": ("legacy.jpg", image_bytes("JPEG"), "image/jpeg")},
        )

    assert response.status_code == 201
    assert [item["image_index"] for item in response.json()["data"]["images"]] == [0, 1]
    assert legacy.status_code == 400
    assert legacy.json()["detail"] == "INVALID_IMAGE_COUNT"


@pytest.mark.parametrize("image_count", [1, 5])
def test_api_accepts_v1_1_image_count_boundaries(image_count: int):
    service, _, _, _ = make_service()
    files = [
        ("images", (f"image-{index}.png", image_bytes("PNG"), "image/png"))
        for index in range(image_count)
    ]

    with TestClient(make_food_api(service)) as client:
        response = client.post("/api/food/recognitions", files=files)

    assert response.status_code == 201
    assert response.json()["code"] == 201
    assert len(response.json()["data"]["images"]) == image_count


@pytest.mark.parametrize(
    ("request_kwargs", "case"),
    [
        ({}, "missing-images-field"),
        (
            {
                "content": b"--empty-images--\r\n",
                "headers": {"content-type": "multipart/form-data; boundary=empty-images"},
            },
            "empty-multipart",
        ),
    ],
)
def test_api_zero_images_returns_v1_invalid_image_count(request_kwargs, case: str):
    service, _, _, _ = make_service()

    with TestClient(make_food_api(service)) as client:
        response = client.post("/api/food/recognitions", **request_kwargs)

    assert case
    assert response.status_code == 400
    assert response.json() == {
        "code": 400,
        "message": "图片数量必须为 1 至 5 张",
        "detail": "INVALID_IMAGE_COUNT",
    }


def test_api_six_images_returns_v1_invalid_image_count():
    service, _, _, _ = make_service()
    files = [
        ("images", (f"image-{index}.png", image_bytes("PNG"), "image/png"))
        for index in range(6)
    ]

    with TestClient(make_food_api(service)) as client:
        response = client.post("/api/food/recognitions", files=files)

    assert response.status_code == 400
    assert response.json()["code"] == 400
    assert response.json()["detail"] == "INVALID_IMAGE_COUNT"


def test_food_upload_openapi_keeps_the_only_public_images_field():
    service, _, _, _ = make_service()

    with TestClient(make_food_api(service)) as client:
        schema = client.get("/openapi.json").json()

    properties = schema["paths"]["/api/food/recognitions"]["post"]["requestBody"]["content"][
        "multipart/form-data"
    ]["schema"]["properties"]
    assert set(properties) == {"images", "conf_threshold"}
