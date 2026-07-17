"""Food 模块 V1 契约、Repository 与 API 回归测试。"""

import json
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

import pytest
from alembic import command
from alembic.config import Config
from fastapi import FastAPI, UploadFile
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect

from app.api.food import file_router, get_food_recognition_service, router
from app.config.settings import settings
from app.core.exceptions import AppException, app_exception_handler
from app.core.security import get_current_user
from app.entity.db_models import FoodRecognitionTask, User
from app.entity.food_schemas import (
    ConfirmIngredientsRequest,
    ConfirmedIngredient,
    FoodRecognitionCreateData,
    ModelDetection,
)
from app.repositories.chat_repository import ChatRepository
from app.repositories.food_repository import FoodRepository
from app.repositories.recipe_repository import RecipeRepository
from app.services.food_recognition_provider import (
    FoodModelUnavailableError,
    YoloFoodRecognitionProvider,
    build_food_recognition_provider,
)
from app.services.food_recognition_service import (
    FoodRecognitionAccessDeniedError,
    FoodPersistenceError,
    FoodRecognitionService,
    FoodModelUnavailableServiceError,
    ImageTooLargeError,
    UnsupportedImageTypeError,
)

JPEG_IMAGE = b"\xff\xd8\xff\xe0" + b"JFIF\x00" + b"food-image"
PNG_IMAGE = b"\x89PNG\r\n\x1a\n" + b"food-image"
FIXTURES = Path(__file__).parent / "fixtures"


def make_upload(
    filename: str = "meal.jpg",
    content_type: str = "image/jpeg",
    content: bytes = JPEG_IMAGE,
) -> UploadFile:
    return UploadFile(
        filename=filename,
        file=BytesIO(content),
        headers={"content-type": content_type},
    )


class FakeStorage:
    def __init__(self):
        self.uploads: list[tuple[str, str]] = []
        self.deleted: list[str] = []
        self.objects: dict[str, bytes] = {}

    def upload_file(self, object_name: str, file_path: str) -> str:
        assert Path(file_path).is_file()
        self.uploads.append((object_name, file_path))
        self.objects[object_name] = Path(file_path).read_bytes()
        return f"https://storage.invalid/{object_name}"

    def delete_file(self, object_name: str) -> None:
        self.deleted.append(object_name)
        self.objects.pop(object_name, None)

    def get_file(self, object_name: str) -> bytes:
        return self.objects[object_name]


class RecordingProvider:
    provider_name = "yolo"
    model_version = "food-yolo-v1"

    def __init__(self, *, empty: bool = False):
        self.empty = empty
        self.paths: list[str] = []

    def recognize(self, image_path: str, conf_threshold: float = 0.25) -> list[ModelDetection]:
        self.paths.append(image_path)
        if self.empty:
            return []
        detections = [
            ModelDetection(
                class_name="tomato",
                confidence=0.9321,
                bbox={"x1": 120.4, "y1": 80.2, "x2": 310.7, "y2": 265.1},
            ),
            ModelDetection(
                class_name="egg",
                confidence=0.8812,
                bbox={"x1": 350.0, "y1": 100.0, "x2": 470.0, "y2": 230.0},
            ),
        ]
        return [item for item in detections if item.confidence >= conf_threshold]

    @staticmethod
    def get_display_name(class_name: str) -> str:
        return {"tomato": "番茄", "egg": "鸡蛋"}.get(class_name, class_name)


class UnavailableProvider(RecordingProvider):
    provider_name = "yolo"
    model_version = "food-yolo-v1"

    def recognize(self, image_path: str, conf_threshold: float = 0.25) -> list[ModelDetection]:
        del image_path, conf_threshold
        raise FoodModelUnavailableError("测试模型不可用")


class SecondImageUnavailableProvider(RecordingProvider):
    def recognize(self, image_path: str, conf_threshold: float = 0.25) -> list[ModelDetection]:
        if len(self.paths) == 1:
            self.paths.append(image_path)
            raise FoodModelUnavailableError("第二张图片推理失败")
        return super().recognize(image_path, conf_threshold)


def make_service(db, *, provider=None, storage=None) -> tuple[FoodRecognitionService, FakeStorage]:
    storage = storage or FakeStorage()
    return (
        FoodRecognitionService(
            repository=FoodRepository(db),
            provider=provider or RecordingProvider(),
            object_storage=storage,
        ),
        storage,
    )


def create_user(db, suffix: str) -> User:
    user = User(
        username=f"food_{suffix}",
        email=f"food_{suffix}@example.com",
        hashed_password="hash",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def make_api_client(service: FoodRecognitionService, user_id: int) -> TestClient:
    app = FastAPI()
    app.add_exception_handler(AppException, app_exception_handler)
    app.include_router(router)
    app.include_router(file_router)

    async def current_user_override():
        return SimpleNamespace(id=user_id)

    app.dependency_overrides[get_current_user] = current_user_override
    app.dependency_overrides[get_food_recognition_service] = lambda: service
    return TestClient(app)


class TestV1Fixtures:
    def test_food_success_fixture_matches_frozen_response_shape(self):
        payload = json.loads(
            (FIXTURES / "food_recognition_success.json").read_text(encoding="utf-8")
        )
        assert payload["code"] == 201
        parsed = FoodRecognitionCreateData.model_validate(payload["data"])
        assert parsed.recognition_id == 12
        assert parsed.ingredients[0].candidate_id == "det-1"
        assert parsed.ingredients[0].source == "model"

    def test_food_empty_fixture_has_no_candidates(self):
        payload = json.loads((FIXTURES / "food_recognition_empty.json").read_text(encoding="utf-8"))
        parsed = FoodRecognitionCreateData.model_validate(payload["data"])
        assert parsed.ingredients == []

    def test_confirm_request_uses_v1_ingredients_not_legacy_field(self):
        request = ConfirmIngredientsRequest.model_validate(
            {
                "ingredients": [
                    {
                        "name": "番茄",
                        "class_name": "tomato",
                        "quantity": 2,
                        "unit": "个",
                        "source": "model",
                    }
                ]
            }
        )
        assert request.ingredients[0].class_name == "tomato"
        with pytest.raises(Exception):
            ConfirmIngredientsRequest.model_validate({"confirmed_ingredients": []})


class TestFoodRecognitionService:
    @pytest.mark.asyncio
    async def test_creates_one_record_for_multiple_images_and_groups_raw_detections(self, db):
        user = create_user(db, "multiple")
        provider = RecordingProvider()
        service, storage = make_service(db, provider=provider)

        response = await service.create_recognition(
            user_id=user.id,
            images=[
                make_upload("first.jpg", "image/jpeg", JPEG_IMAGE),
                make_upload("second.png", "image/png", PNG_IMAGE),
            ],
            conf_threshold=0.25,
        )

        task = db.get(FoodRecognitionTask, response.recognition_id)
        assert task is not None
        assert len(storage.uploads) == len(provider.paths) == 2
        assert task.image_object_names == [object_name for object_name, _ in storage.uploads]
        assert [item["image_index"] for item in task.raw_detections] == [0, 1]
        assert [
            item["image_object_name"] for item in task.raw_detections
        ] == task.image_object_names
        assert all(len(item["detections"]) == 2 for item in task.raw_detections)
        assert [item.candidate_id for item in response.ingredients] == [
            "det-1",
            "det-2",
            "det-3",
            "det-4",
        ]
        assert [item.image_url for item in response.images] == [
            f"/api/files/food/{response.recognition_id}",
            f"/api/files/food/{response.recognition_id}?image_index=1",
        ]
        assert [[item.candidate_id for item in image.ingredients] for image in response.images] == [
            ["det-1", "det-2"],
            ["det-3", "det-4"],
        ]

        image_content, media_type = await service.get_image(
            user_id=user.id,
            recognition_id=response.recognition_id,
        )
        assert image_content == JPEG_IMAGE
        assert media_type == "image/jpeg"

        second_image_content, second_media_type = await service.get_image(
            user_id=user.id,
            recognition_id=response.recognition_id,
            image_index=1,
        )
        assert second_image_content == PNG_IMAGE
        assert second_media_type == "image/png"

    @pytest.mark.asyncio
    async def test_cleans_every_uploaded_image_when_one_image_inference_fails(self, db):
        user = create_user(db, "cleanup_inference")
        provider = SecondImageUnavailableProvider()
        service, storage = make_service(db, provider=provider)

        with pytest.raises(FoodModelUnavailableServiceError):
            await service.create_recognition(
                user_id=user.id,
                images=[
                    make_upload("first.jpg", "image/jpeg", JPEG_IMAGE),
                    make_upload("second.png", "image/png", PNG_IMAGE),
                ],
                conf_threshold=0.25,
            )

        assert len(storage.uploads) == len(storage.deleted) == 2
        assert storage.objects == {}
        assert db.query(FoodRecognitionTask).count() == 0

    @pytest.mark.asyncio
    async def test_cleans_task_and_images_when_detection_persistence_fails(self, db, monkeypatch):
        user = create_user(db, "cleanup_persistence")
        service, storage = make_service(db)

        def fail_to_save(*args, **kwargs):
            raise RuntimeError("模拟保存失败")

        monkeypatch.setattr(service.repository, "save_raw_detections", fail_to_save)
        with pytest.raises(FoodPersistenceError):
            await service.create_recognition(
                user_id=user.id,
                images=[make_upload()],
                conf_threshold=0.25,
            )

        assert len(storage.uploads) == len(storage.deleted) == 1
        assert storage.objects == {}
        assert db.query(FoodRecognitionTask).count() == 0

    @pytest.mark.asyncio
    async def test_creates_persistent_v1_record_and_removes_temp_file(self, db):
        user = create_user(db, "create")
        provider = RecordingProvider()
        service, storage = make_service(db, provider=provider)

        response = await service.create_recognition(
            user_id=user.id,
            images=[make_upload()],
            conf_threshold=0.25,
        )

        assert response.recognition_id > 0
        assert response.status == "completed"
        assert response.provider == "yolo"
        assert response.image_url == f"/api/files/food/{response.recognition_id}"
        assert [item.class_name for item in response.ingredients] == ["tomato", "egg"]
        assert all(item.source == "model" for item in response.ingredients)
        assert response.created_at.isoformat().endswith("+08:00")
        task = db.get(FoodRecognitionTask, response.recognition_id)
        assert task is not None
        assert task.confirmed_ingredients == []
        assert task.image_object_names == [storage.uploads[0][0]]
        assert task.raw_detections[0]["image_index"] == 0
        assert task.raw_detections[0]["image_object_name"] == storage.uploads[0][0]
        assert task.raw_detections[0]["detections"][0]["class_name"] == "tomato"
        assert storage.uploads
        assert not Path(storage.uploads[0][1]).exists()
        assert all(Path(path).is_absolute() for path in provider.paths)

    @pytest.mark.asyncio
    async def test_empty_model_result_is_a_successful_empty_list(self, db):
        user = create_user(db, "empty")
        service, _ = make_service(db, provider=RecordingProvider(empty=True))

        response = await service.create_recognition(
            user_id=user.id,
            images=[make_upload()],
            conf_threshold=0.25,
        )

        assert response.status == "completed"
        assert response.ingredients == []

    @pytest.mark.asyncio
    async def test_rejects_oversized_and_non_image_uploads(self, db):
        user = create_user(db, "validation")
        service, _ = make_service(db)
        oversized = JPEG_IMAGE + (b"x" * FoodRecognitionService.MAX_UPLOAD_BYTES)

        with pytest.raises(ImageTooLargeError):
            await service.create_recognition(
                user_id=user.id,
                images=[make_upload(content=oversized)],
                conf_threshold=0.25,
            )
        with pytest.raises(UnsupportedImageTypeError):
            await service.create_recognition(
                user_id=user.id,
                images=[make_upload("meal.gif", "image/gif", b"GIF89a")],
                conf_threshold=0.25,
            )

    @pytest.mark.asyncio
    async def test_confirm_overwrites_snapshot_and_enforces_user_ownership(self, db):
        owner = create_user(db, "owner")
        other = create_user(db, "other")
        service, _ = make_service(db)
        created = await service.create_recognition(
            user_id=owner.id,
            images=[make_upload()],
            conf_threshold=0.25,
        )

        first = service.confirm_ingredients(
            user_id=owner.id,
            recognition_id=created.recognition_id,
            ingredients=[
                ConfirmedIngredient(
                    name="番茄", class_name="tomato", quantity=2, unit="个", source="model"
                ),
                ConfirmedIngredient(
                    name="番茄", class_name="tomato", quantity=3, unit="个", source="model"
                ),
                ConfirmedIngredient(
                    name="鸡蛋", class_name="egg", quantity=3, unit="个", source="manual"
                ),
            ],
        )
        second = service.confirm_ingredients(
            user_id=owner.id,
            recognition_id=created.recognition_id,
            ingredients=[
                ConfirmedIngredient(
                    name="鸡蛋", class_name=None, quantity=1, unit="个", source="manual"
                )
            ],
        )

        assert len(first.confirmed_ingredients) == 2
        assert first.confirmed_ingredients[0].name == "番茄"
        assert first.confirmed_ingredients[0].quantity == 5
        persisted = db.get(FoodRecognitionTask, created.recognition_id)
        assert persisted is not None
        assert persisted.confirmed_ingredients == [
            {"name": "番茄", "class_name": "tomato", "quantity": 5, "unit": "个", "source": "model"},
            {"name": "鸡蛋", "class_name": "egg", "quantity": 3, "unit": "个", "source": "manual"},
        ]
        assert [item.name for item in second.confirmed_ingredients] == ["鸡蛋"]
        with pytest.raises(FoodRecognitionAccessDeniedError):
            service.get_recognition(user_id=other.id, recognition_id=created.recognition_id)


class TestRepositories:
    @pytest.mark.asyncio
    async def test_recipe_and_chat_repositories_work_with_food_task(self, db):
        user = create_user(db, "repositories")
        food_service, _ = make_service(db)
        recognition = await food_service.create_recognition(
            user_id=user.id,
            images=[make_upload()],
            conf_threshold=0.25,
        )
        recipe_repository = RecipeRepository(db)
        recipe = recipe_repository.create_recipe(
            user.id,
            recognition.recognition_id,
            {"title": "番茄炒蛋", "servings": 2},
            {"provider": "fake", "model": "fixture-v1", "is_mock": True},
        )
        updated = recipe_repository.save_new_recipe_version(
            recipe.id,
            user.id,
            {"title": "少油版番茄炒蛋", "servings": 3},
        )
        chat_repository = ChatRepository(db)
        session = chat_repository.create_session(user.id, recipe.id)
        message = chat_repository.save_message(session.id, "user", "改成三人份")

        assert updated is not None and updated.version == 2
        assert session.recipe_id == recipe.id
        assert message.session_id == session.id
        assert chat_repository.get_session_for_user(session.id, user.id) is not None


class TestFoodMigration:
    def test_upgrade_and_downgrade_food_v1_schema(self, tmp_path):
        database_url = f"sqlite:///{tmp_path / 'food_v1.sqlite'}"
        previous_database_url = settings.DATABASE_URL
        config = Config(str(Path(__file__).parents[1] / "alembic.ini"))
        try:
            settings.DATABASE_URL = database_url
            command.upgrade(config, "head")
            engine = create_engine(database_url)
            inspector = inspect(engine)
            assert {"food_recognition_tasks", "recipes"}.issubset(inspector.get_table_names())
            assert "image_object_names" in {
                column["name"] for column in inspector.get_columns("food_recognition_tasks")
            }
            assert "recipe_id" in {
                column["name"] for column in inspector.get_columns("chat_sessions")
            }
            engine.dispose()

            command.downgrade(config, "b4d91f0c2a7e")
            engine = create_engine(database_url)
            inspector = inspect(engine)
            assert "image_object_name" in {
                column["name"] for column in inspector.get_columns("food_recognition_tasks")
            }
            assert "image_object_names" not in {
                column["name"] for column in inspector.get_columns("food_recognition_tasks")
            }
            assert "recipe_id" in {
                column["name"] for column in inspector.get_columns("chat_sessions")
            }
            engine.dispose()

            command.downgrade(config, "base")
            engine = create_engine(database_url)
            inspector = inspect(engine)
            assert "food_recognition_tasks" not in inspector.get_table_names()
            assert "recipes" not in inspector.get_table_names()
            engine.dispose()
        finally:
            settings.DATABASE_URL = previous_database_url


class TestFoodApi:
    def test_main_app_registers_exact_v1_food_routes(self):
        from main import app

        paths = app.openapi()["paths"]
        assert "/api/food/recognitions" in paths
        assert "/api/food/recognitions/{recognition_id}" in paths
        assert "/api/food/recognitions/{recognition_id}/ingredients" in paths
        assert "/api/food/recognitions/{recognition_id}/confirmed-ingredients" not in paths

    def test_create_get_confirm_and_cross_user_forbidden(self, db):
        owner = create_user(db, "apiowner")
        other = create_user(db, "apiother")
        service, _ = make_service(db)

        with make_api_client(service, owner.id) as client:
            created = client.post(
                "/api/food/recognitions",
                data={"conf_threshold": "0.25"},
                files={"image": ("meal.jpg", JPEG_IMAGE, "image/jpeg")},
            )
            assert created.status_code == 201
            assert created.json()["message"] == "识别完成"
            recognition_id = created.json()["data"]["recognition_id"]

            queried = client.get(f"/api/food/recognitions/{recognition_id}")
            assert queried.status_code == 200
            assert queried.json()["data"]["confirmed_ingredients"] == []

            image = client.get(f"/api/files/food/{recognition_id}")
            assert image.status_code == 200
            assert image.content == JPEG_IMAGE
            assert image.headers["content-type"] == "image/jpeg"

            confirmed = client.put(
                f"/api/food/recognitions/{recognition_id}/ingredients",
                json={
                    "ingredients": [
                        {
                            "name": "番茄",
                            "class_name": "tomato",
                            "quantity": 2,
                            "unit": "个",
                            "source": "model",
                        }
                    ]
                },
            )
            assert confirmed.status_code == 200
            assert confirmed.json()["message"] == "食材已确认"

        with make_api_client(service, other.id) as client:
            forbidden = client.get(f"/api/food/recognitions/{recognition_id}")
            assert forbidden.status_code == 403
            assert forbidden.json() == {"code": 403, "message": "无权访问该识别记录", "data": None}

    def test_api_uses_images_as_the_primary_multi_file_field(self, db):
        user = create_user(db, "apimultiple")
        service, storage = make_service(db)

        with make_api_client(service, user.id) as client:
            created = client.post(
                "/api/food/recognitions",
                files=[
                    ("images", ("first.jpg", JPEG_IMAGE, "image/jpeg")),
                    ("images", ("second.png", PNG_IMAGE, "image/png")),
                ],
            )

        assert created.status_code == 201
        recognition_id = created.json()["data"]["recognition_id"]
        task = db.get(FoodRecognitionTask, recognition_id)
        assert task is not None
        assert task.image_object_names == [object_name for object_name, _ in storage.uploads]
        assert len(task.raw_detections) == 2
        assert len(created.json()["data"]["ingredients"]) == 4
        assert [image["image_index"] for image in created.json()["data"]["images"]] == [0, 1]
        assert created.json()["data"]["images"][1]["image_url"] == (
            f"/api/files/food/{recognition_id}?image_index=1"
        )

        with make_api_client(service, user.id) as client:
            detail = client.get(f"/api/food/recognitions/{recognition_id}")
            second_image = client.get(f"/api/files/food/{recognition_id}?image_index=1")
            missing_image = client.get(f"/api/files/food/{recognition_id}?image_index=2")

        assert detail.status_code == 200
        assert [image["image_index"] for image in detail.json()["data"]["images"]] == [0, 1]
        assert [
            [ingredient["candidate_id"] for ingredient in image["ingredients"]]
            for image in detail.json()["data"]["images"]
        ] == [["det-1", "det-2"], ["det-3", "det-4"]]
        assert second_image.status_code == 200
        assert second_image.content == PNG_IMAGE
        assert second_image.headers["content-type"] == "image/png"
        assert missing_image.status_code == 400
        assert missing_image.json() == {"code": 400, "message": "图片序号不存在", "data": None}

    def test_api_maps_image_and_model_errors_to_v1_status_codes(self, db):
        user = create_user(db, "apierrors")
        unavailable_service, _ = make_service(db, provider=UnavailableProvider())
        with make_api_client(unavailable_service, user.id) as client:
            model_error = client.post(
                "/api/food/recognitions",
                files={"image": ("meal.jpg", JPEG_IMAGE, "image/jpeg")},
            )
            too_large = client.post(
                "/api/food/recognitions",
                files={
                    "image": (
                        "meal.jpg",
                        JPEG_IMAGE + (b"x" * FoodRecognitionService.MAX_UPLOAD_BYTES),
                        "image/jpeg",
                    )
                },
            )
            invalid_type = client.post(
                "/api/food/recognitions",
                files={"image": ("meal.gif", b"GIF89a", "image/gif")},
            )
        assert model_error.status_code == 503
        assert model_error.json() == {
            "code": 503,
            "message": "食物识别模型暂不可用",
            "data": None,
        }
        assert too_large.status_code == 413
        assert invalid_type.status_code == 415


class TestProviders:
    def test_default_provider_uses_delivered_yolo_model(self):
        provider = build_food_recognition_provider()

        assert isinstance(provider, YoloFoodRecognitionProvider)
        assert provider.model_path.is_file()
        assert provider.classes_path.is_file()
        assert provider.provider_name == "yolo"
        assert provider.model_version == "food-yolo-v1"
        assert provider.get_display_name("sugar") == "糖"
        assert build_food_recognition_provider() is provider

    def test_yolo_provider_reports_unavailable_without_weights(self, tmp_path):
        classes_path = Path(__file__).parents[1] / "scripts" / "food_model" / "classes.yaml"
        provider = YoloFoodRecognitionProvider(
            model_path=str(tmp_path / "missing.pt"),
            classes_path=str(classes_path),
        )
        with pytest.raises(FoodModelUnavailableError):
            provider.recognize(str(tmp_path / "meal.jpg"))

    @pytest.mark.asyncio
    async def test_configured_yolo_without_files_maps_to_api_503(self, db, monkeypatch, tmp_path):
        user = create_user(db, "configuredyolo")
        classes_path = Path(__file__).parents[1] / "scripts" / "food_model" / "classes.yaml"
        monkeypatch.setattr(settings, "FOOD_MODEL_PATH", str(tmp_path / "missing.pt"))
        monkeypatch.setattr(settings, "FOOD_CLASSES_PATH", str(classes_path))
        provider = build_food_recognition_provider()
        service, _ = make_service(db, provider=provider)

        with pytest.raises(FoodModelUnavailableServiceError):
            await service.create_recognition(
                user_id=user.id,
                images=[make_upload()],
                conf_threshold=0.25,
            )
