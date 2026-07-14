"""食物识别 Day 2：上传、YOLO 结果、持久化边界与 API 契约测试。"""
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import FastAPI, UploadFile
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.api.food import get_food_recognition_service, router
from app.core.exceptions import AppException, app_exception_handler
from app.core.security import get_current_user
from app.entity.food_schemas import (
    BoundingBox,
    ConfirmIngredientsRequest,
    ConfirmedIngredient,
    IngredientCandidate,
)
from app.services.food_recognition_provider import (
    FoodRecognitionProviderError,
    FoodRecognitionProviderUnavailable,
)
from app.services.food_recognition_service import (
    FoodRecognitionPersistenceError,
    FoodRecognitionRecord,
    FoodRecognitionService,
    FoodRecognitionStorageError,
    FoodRecognitionValidationError,
)

JPEG_IMAGE = b"\xff\xd8\xff\xe0" + b"JFIF\x00" + b"food-image"
PNG_IMAGE = b"\x89PNG\r\n\x1a\n" + b"food-image"


def make_upload(filename: str, content_type: str, content: bytes = JPEG_IMAGE) -> UploadFile:
    """构造带 MIME 类型的单文件上传对象。"""
    return UploadFile(filename=filename, file=BytesIO(content), headers={"content-type": content_type})


def copy_record(record: FoodRecognitionRecord) -> FoodRecognitionRecord:
    """模拟 ORM 读写边界，避免测试通过共享内存对象偶然成功。"""
    return FoodRecognitionRecord(
        user_id=record.user_id,
        recognition=record.recognition.model_copy(deep=True),
        image_mime_type=record.image_mime_type,
        image_size=record.image_size,
        error_message=record.error_message,
    )


class FakeRepository:
    """仅位于测试文件中的 Repository Fake。"""

    def __init__(self):
        self.records: dict[str, FoodRecognitionRecord] = {}

    async def create(self, record: FoodRecognitionRecord) -> FoodRecognitionRecord:
        stored = copy_record(record)
        self.records[stored.recognition.recognition_id] = stored
        return copy_record(stored)

    async def get(self, recognition_id: str) -> FoodRecognitionRecord | None:
        record = self.records.get(recognition_id)
        return copy_record(record) if record else None

    async def update(self, record: FoodRecognitionRecord) -> FoodRecognitionRecord | None:
        if record.recognition.recognition_id not in self.records:
            return None
        return await self.create(record)


class FailingRepository(FakeRepository):
    async def create(self, record: FoodRecognitionRecord) -> FoodRecognitionRecord:
        raise RuntimeError("database unavailable")


class FakeStorage:
    """隔离 MinIO，并保留临时路径以验证 finally 清理。"""

    def __init__(self):
        self.uploads: list[tuple[str, str]] = []
        self.deleted_objects: list[str] = []

    def upload_file(self, object_name: str, file_path: str) -> str:
        self.uploads.append((object_name, file_path))
        assert Path(file_path).is_file()
        return f"https://storage.invalid/{object_name}"

    def delete_file(self, object_name: str) -> None:
        self.deleted_objects.append(object_name)


class FailingStorage(FakeStorage):
    def upload_file(self, object_name: str, file_path: str) -> str:
        self.uploads.append((object_name, file_path))
        assert Path(file_path).is_file()
        raise RuntimeError("minio unavailable")


class FakeProvider:
    """测试专属的 YOLO Provider Fake。"""

    model_version = "fake-food-yolo-v1"

    def __init__(self):
        self.image_paths: list[str] = []

    async def recognize(self, image_path: str, conf_threshold: float):
        self.image_paths.append(image_path)
        return [
            {
                "key": " Tomato ",
                "name": "tomato",
                "confidence": 0.95,
                "bbox": {"x1": 1, "y1": 2, "x2": 20, "y2": 30},
            },
            {"key": "tomato", "name": "番茄", "confidence": 0.80},
            {"key": "cucumber", "name": "黄瓜", "confidence": 0.20},
        ]


class EmptyProvider(FakeProvider):
    async def recognize(self, image_path: str, conf_threshold: float):
        self.image_paths.append(image_path)
        return []


class FailingProvider(FakeProvider):
    async def recognize(self, image_path: str, conf_threshold: float):
        self.image_paths.append(image_path)
        raise FoodRecognitionProviderUnavailable("测试用 YOLO 不可用")


class InvalidResultProvider(FakeProvider):
    async def recognize(self, image_path: str, conf_threshold: float):
        self.image_paths.append(image_path)
        return [{"key": "tomato", "name": "番茄", "confidence": float("nan")}]


def make_service(
    provider: FakeProvider | None = None,
    repository: FakeRepository | None = None,
    storage: FakeStorage | None = None,
    *,
    max_upload_bytes: int | None = None,
) -> tuple[FoodRecognitionService, FakeRepository, FakeStorage]:
    repository = repository or FakeRepository()
    storage = storage or FakeStorage()
    return (
        FoodRecognitionService(
            provider=provider or FakeProvider(),
            repository=repository,
            object_storage=storage,
            max_upload_bytes=max_upload_bytes,
        ),
        repository,
        storage,
    )


def make_api_client(service: FoodRecognitionService, *, user_id: int = 7) -> TestClient:
    """将 food router 单独装配，以便覆盖认证与持久化依赖。"""
    app = FastAPI()
    app.add_exception_handler(AppException, app_exception_handler)
    app.include_router(router)

    async def override_current_user():
        return SimpleNamespace(id=user_id)

    app.dependency_overrides[get_current_user] = override_current_user
    app.dependency_overrides[get_food_recognition_service] = lambda: service
    return TestClient(app)


class TestFoodRecognitionSchemas:
    def test_bbox_and_confidence_reject_non_finite_json_numbers(self):
        with pytest.raises(ValidationError):
            BoundingBox(x1=0, y1=0, x2=float("inf"), y2=1)
        with pytest.raises(ValidationError):
            IngredientCandidate(key="tomato", name="番茄", confidence=float("nan"))

    def test_confirmed_keys_are_normalized_before_duplicate_validation(self):
        ingredient = {"key": " Tomato ", "name": "番茄", "source": "manual"}
        with pytest.raises(ValidationError, match="不允许重复"):
            ConfirmIngredientsRequest(confirmed_ingredients=[ingredient, {**ingredient, "key": "tomato"}])


class TestFoodRecognitionService:
    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("filename", "content_type", "content"),
        [("meal.jpg", "image/jpeg", JPEG_IMAGE), ("meal.png", "image/png", PNG_IMAGE)],
    )
    async def test_valid_image_creates_json_safe_persistent_record(
        self, filename, content_type, content
    ):
        service, repository, storage = make_service()

        result = await service.create_recognition(
            user_id=7,
            image=make_upload(filename, content_type, content),
            conf_threshold=0.5,
        )

        assert result.provider == "yolo"
        assert result.image_object_name.startswith("food-recognitions/7/")
        assert result.image_object_name.endswith(Path(filename).suffix)
        assert [(candidate.key, candidate.name) for candidate in result.raw_detections] == [("tomato", "番茄")]
        persisted = repository.records[result.recognition_id].as_persistence_payload()
        assert persisted["image_mime_type"] == content_type
        assert persisted["raw_detections"][0]["key"] == "tomato"
        assert all("path" not in field_name for field_name in persisted)
        assert all(not Path(path).exists() for _, path in storage.uploads)

    @pytest.mark.asyncio
    async def test_empty_detection_creates_task_and_allows_manual_confirmation(self):
        service, _, _ = make_service(provider=EmptyProvider())
        recognition = await service.create_recognition(
            user_id=7,
            image=make_upload("meal.jpg", "image/jpeg"),
            conf_threshold=0.5,
        )

        confirmed = await service.confirm_ingredients(
            user_id=7,
            recognition_id=recognition.recognition_id,
            confirmed_ingredients=[
                ConfirmedIngredient(key="egg", name="鸡蛋", quantity="2", unit="个", source="manual")
            ],
        )

        assert recognition.raw_detections == []
        assert confirmed.status == "confirmed"
        assert confirmed.confirmed_ingredients[0].source == "manual"

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("filename", "content_type", "content"),
        [
            ("meal.gif", "image/gif", JPEG_IMAGE),
            ("meal.jpg", "image/png", JPEG_IMAGE),
            ("meal.jpg", "image/jpeg", b"not-a-jpeg"),
        ],
    )
    async def test_invalid_extension_mime_or_header_is_rejected(self, filename, content_type, content):
        service, _, _ = make_service()
        with pytest.raises(FoodRecognitionValidationError):
            await service.create_recognition(
                user_id=7,
                image=make_upload(filename, content_type, content),
                conf_threshold=0.5,
            )

    @pytest.mark.asyncio
    async def test_oversized_file_and_invalid_threshold_are_rejected(self):
        service, _, _ = make_service(max_upload_bytes=len(JPEG_IMAGE))
        with pytest.raises(FoodRecognitionValidationError, match="不能超过"):
            await service.create_recognition(
                user_id=7,
                image=make_upload("meal.jpg", "image/jpeg", JPEG_IMAGE + b"x"),
                conf_threshold=0.5,
            )
        with pytest.raises(FoodRecognitionValidationError, match="0 到 1"):
            await service.create_recognition(
                user_id=7,
                image=make_upload("meal.jpg", "image/jpeg"),
                conf_threshold=float("nan"),
            )

    @pytest.mark.asyncio
    async def test_provider_failure_creates_failed_record_and_cleans_temp_file(self):
        provider = FailingProvider()
        service, repository, storage = make_service(provider=provider)

        with pytest.raises(FoodRecognitionProviderUnavailable):
            await service.create_recognition(
                user_id=7,
                image=make_upload("meal.jpg", "image/jpeg"),
                conf_threshold=0.5,
            )

        failed_record = next(iter(repository.records.values()))
        assert failed_record.recognition.status == "failed"
        assert failed_record.error_message == "测试用 YOLO 不可用"
        assert all(not Path(path).exists() for _, path in storage.uploads)
        assert all(not Path(path).exists() for path in provider.image_paths)

    @pytest.mark.asyncio
    async def test_storage_failure_creates_failed_record_and_cleans_temp_file(self):
        storage = FailingStorage()
        service, repository, _ = make_service(storage=storage)

        with pytest.raises(FoodRecognitionStorageError):
            await service.create_recognition(
                user_id=7,
                image=make_upload("meal.jpg", "image/jpeg"),
                conf_threshold=0.5,
            )

        failed_record = next(iter(repository.records.values()))
        assert failed_record.recognition.status == "failed"
        assert failed_record.error_message == "食物图片存储服务不可用"
        assert all(not Path(path).exists() for _, path in storage.uploads)

    @pytest.mark.asyncio
    async def test_invalid_provider_result_is_rejected_and_recorded_as_failed(self):
        service, repository, _ = make_service(provider=InvalidResultProvider())
        with pytest.raises(FoodRecognitionProviderError):
            await service.create_recognition(
                user_id=7,
                image=make_upload("meal.jpg", "image/jpeg"),
                conf_threshold=0.5,
            )
        assert next(iter(repository.records.values())).recognition.status == "failed"

    @pytest.mark.asyncio
    async def test_database_failure_compensates_uploaded_object(self):
        repository = FailingRepository()
        storage = FakeStorage()
        service, _, _ = make_service(repository=repository, storage=storage)

        with pytest.raises(FoodRecognitionPersistenceError):
            await service.create_recognition(
                user_id=7,
                image=make_upload("meal.jpg", "image/jpeg"),
                conf_threshold=0.5,
            )

        assert storage.deleted_objects == [storage.uploads[0][0]]
        assert not Path(storage.uploads[0][1]).exists()

    @pytest.mark.asyncio
    async def test_no_repository_is_not_treated_as_in_memory_persistence(self):
        service = FoodRecognitionService(provider=FakeProvider(), object_storage=FakeStorage())
        with pytest.raises(FoodRecognitionPersistenceError, match="尚未接入"):
            await service.create_recognition(
                user_id=7,
                image=make_upload("meal.jpg", "image/jpeg"),
                conf_threshold=0.5,
            )


class TestFoodRecognitionApi:
    def test_all_food_routes_declare_authentication_dependency(self):
        food_routes = [route for route in router.routes if isinstance(route, APIRoute)]
        assert len(food_routes) == 3
        for route in food_routes:
            assert any(dependency.call is get_current_user for dependency in route.dependant.dependencies)

    def test_create_get_and_complete_confirmation_overwrite(self):
        service, _, _ = make_service()
        with make_api_client(service) as client:
            create = client.post(
                "/api/food/recognitions",
                data={"conf_threshold": "0.5"},
                files={"image": ("meal.jpg", JPEG_IMAGE, "image/jpeg")},
            )
            assert create.status_code == 201
            recognition_id = create.json()["data"]["recognition_id"]

            queried = client.get(f"/api/food/recognitions/{recognition_id}")
            assert queried.status_code == 200
            assert queried.json()["data"]["recognition_id"] == recognition_id

            first = client.put(
                f"/api/food/recognitions/{recognition_id}/confirmed-ingredients",
                json={
                    "confirmed_ingredients": [
                        {"key": "tomato", "name": "番茄", "source": "yolo"},
                        {"key": "egg", "name": "鸡蛋", "source": "manual"},
                    ]
                },
            )
            assert first.status_code == 200

            second = client.put(
                f"/api/food/recognitions/{recognition_id}/confirmed-ingredients",
                json={"confirmed_ingredients": [{"key": "egg", "name": "鸡蛋", "source": "manual"}]},
            )
            assert second.status_code == 200
            assert [item["key"] for item in second.json()["data"]["confirmed_ingredients"]] == ["egg"]

    def test_get_other_users_task_is_forbidden(self):
        service, _, _ = make_service()
        with make_api_client(service, user_id=7) as owner_client:
            created = owner_client.post(
                "/api/food/recognitions",
                files={"image": ("meal.jpg", JPEG_IMAGE, "image/jpeg")},
            )
        recognition_id = created.json()["data"]["recognition_id"]

        with make_api_client(service, user_id=8) as other_client:
            response = other_client.get(f"/api/food/recognitions/{recognition_id}")

        assert response.status_code == 403
        assert response.json()["code"] == 403

    def test_empty_or_duplicate_confirmation_is_rejected(self):
        service, _, _ = make_service()
        with make_api_client(service) as client:
            created = client.post(
                "/api/food/recognitions",
                files={"image": ("meal.jpg", JPEG_IMAGE, "image/jpeg")},
            )
            recognition_id = created.json()["data"]["recognition_id"]
            empty = client.put(
                f"/api/food/recognitions/{recognition_id}/confirmed-ingredients",
                json={"confirmed_ingredients": []},
            )
            duplicate = client.put(
                f"/api/food/recognitions/{recognition_id}/confirmed-ingredients",
                json={
                    "confirmed_ingredients": [
                        {"key": "tomato", "name": "番茄", "source": "yolo"},
                        {"key": "Tomato", "name": "番茄", "source": "manual"},
                    ]
                },
            )

        assert empty.status_code == 422
        assert duplicate.status_code == 422

    @pytest.mark.parametrize("failure", ["storage", "provider"])
    def test_minio_and_provider_failures_map_to_503(self, failure):
        if failure == "storage":
            service, _, _ = make_service(storage=FailingStorage())
        else:
            service, _, _ = make_service(provider=FailingProvider())

        with make_api_client(service) as client:
            response = client.post(
                "/api/food/recognitions",
                files={"image": ("meal.jpg", JPEG_IMAGE, "image/jpeg")},
            )

        assert response.status_code == 503
        assert response.json()["code"] == 503

    def test_openapi_schema_contains_all_food_endpoints(self):
        service, _, _ = make_service()
        with make_api_client(service) as client:
            schema = client.get("/openapi.json").json()

        assert "/api/food/recognitions" in schema["paths"]
        assert "/api/food/recognitions/{recognition_id}" in schema["paths"]
        assert "/api/food/recognitions/{recognition_id}/confirmed-ingredients" in schema["paths"]
