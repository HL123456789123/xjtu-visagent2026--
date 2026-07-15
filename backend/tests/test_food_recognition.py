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
    MockFoodRecognitionProvider,
    YoloFoodRecognitionProvider,
    build_food_recognition_provider,
)
from app.services.food_recognition_service import (
    FoodRecognitionAccessDeniedError,
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


class RecordingProvider(MockFoodRecognitionProvider):
    def __init__(self, *, empty: bool = False):
        self.empty = empty
        self.paths: list[str] = []

    def recognize(self, image_path: str, conf_threshold: float = 0.25) -> list[ModelDetection]:
        self.paths.append(image_path)
        if self.empty:
            return []
        return [
            ModelDetection.model_validate(item)
            for item in super().recognize(image_path, conf_threshold)
        ]


class UnavailableProvider(MockFoodRecognitionProvider):
    provider_name = "yolo"
    model_version = "food-yolo-v1"

    def recognize(self, image_path: str, conf_threshold: float = 0.25) -> list[ModelDetection]:
        del image_path, conf_threshold
        raise FoodModelUnavailableError("测试模型不可用")


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
    async def test_creates_persistent_v1_record_and_removes_temp_file(self, db):
        user = create_user(db, "create")
        provider = RecordingProvider()
        service, storage = make_service(db, provider=provider)

        response = await service.create_recognition(
            user_id=user.id,
            image=make_upload(),
            conf_threshold=0.25,
        )

        assert response.recognition_id > 0
        assert response.status == "completed"
        assert response.provider == "mock"
        assert response.image_url == f"/api/files/food/{response.recognition_id}"
        assert [item.class_name for item in response.ingredients] == ["tomato", "egg"]
        assert all(item.source == "model" for item in response.ingredients)
        assert response.created_at.isoformat().endswith("+08:00")
        task = db.get(FoodRecognitionTask, response.recognition_id)
        assert task is not None
        assert task.confirmed_ingredients == []
        assert task.raw_detections[0]["candidate_id"] == "det-1"
        assert storage.uploads
        assert not Path(storage.uploads[0][1]).exists()
        assert all(Path(path).is_absolute() for path in provider.paths)

    @pytest.mark.asyncio
    async def test_empty_model_result_is_a_successful_empty_list(self, db):
        user = create_user(db, "empty")
        service, _ = make_service(db, provider=RecordingProvider(empty=True))

        response = await service.create_recognition(
            user_id=user.id,
            image=make_upload(),
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
                image=make_upload(content=oversized),
                conf_threshold=0.25,
            )
        with pytest.raises(UnsupportedImageTypeError):
            await service.create_recognition(
                user_id=user.id,
                image=make_upload("meal.gif", "image/gif", b"GIF89a"),
                conf_threshold=0.25,
            )

    @pytest.mark.asyncio
    async def test_confirm_overwrites_snapshot_and_enforces_user_ownership(self, db):
        owner = create_user(db, "owner")
        other = create_user(db, "other")
        service, _ = make_service(db)
        created = await service.create_recognition(
            user_id=owner.id,
            image=make_upload(),
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
            image=make_upload(),
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
            assert "recipe_id" in {
                column["name"] for column in inspector.get_columns("chat_sessions")
            }
            engine.dispose()

            command.downgrade(config, "-1")
            engine = create_engine(database_url)
            inspector = inspect(engine)
            assert "food_recognition_tasks" not in inspector.get_table_names()
            assert "recipes" not in inspector.get_table_names()
            assert "recipe_id" not in {
                column["name"] for column in inspector.get_columns("chat_sessions")
            }
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
    def test_mock_provider_follows_frozen_model_interface(self):
        result = MockFoodRecognitionProvider().recognize("/tmp/example.jpg", 0.25)
        assert all(isinstance(item, ModelDetection) for item in result)
        assert result[0].class_name == "tomato"

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
        monkeypatch.setattr(settings, "FOOD_PROVIDER", "yolo")
        monkeypatch.setattr(settings, "FOOD_MODEL_PATH", str(tmp_path / "missing.pt"))
        monkeypatch.setattr(settings, "FOOD_CLASSES_PATH", str(classes_path))
        provider = build_food_recognition_provider()
        service, _ = make_service(db, provider=provider)

        with pytest.raises(FoodModelUnavailableServiceError):
            await service.create_recognition(
                user_id=user.id,
                image=make_upload(),
                conf_threshold=0.25,
            )
