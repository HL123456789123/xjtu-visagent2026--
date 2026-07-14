"""食物识别 DTO、服务骨架和 API 路由测试。"""
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
from app.services.food_recognition_provider import FoodRecognitionProviderUnavailable
from app.services.food_recognition_service import (
    FoodRecognitionService,
    FoodRecognitionValidationError,
    InMemoryFoodRecognitionRepository,
)


class FakeStorage:
    """隔离 MinIO 的测试存储实现。"""

    def __init__(self):
        self.uploads: list[tuple[str, str]] = []

    def upload_file(self, object_name: str, file_path: str) -> str:
        self.uploads.append((object_name, file_path))
        return f"https://storage.invalid/{object_name}"


class FakeProvider:
    """测试文件内定义的 Provider，不是生产 Mock Provider。"""

    model_version = "fake-food-yolo-v1"

    async def recognize(self, image_path: str, conf_threshold: float):
        return [
            IngredientCandidate(
                key="tomato",
                name="番茄",
                confidence=0.95,
                bbox=BoundingBox(x1=1, y1=2, x2=20, y2=30),
            ),
            IngredientCandidate(
                key="tomato",
                name="番茄",
                confidence=0.80,
                bbox=BoundingBox(x1=3, y1=4, x2=18, y2=28),
            ),
            IngredientCandidate(key="cucumber", name="黄瓜", confidence=0.20),
        ]


class FailingProvider:
    """模拟模型不可用，验证 API 的 503 映射。"""

    model_version = "fake-food-yolo-v1"

    async def recognize(self, image_path: str, conf_threshold: float):
        raise FoodRecognitionProviderUnavailable("测试用 YOLO 不可用")


def make_upload(filename: str, content_type: str, content: bytes = b"image") -> UploadFile:
    """构造独立于 HTTP Client 的上传对象。"""
    from io import BytesIO

    return UploadFile(filename=filename, file=BytesIO(content), headers={"content-type": content_type})


def make_service(provider=None, *, max_upload_bytes=None) -> FoodRecognitionService:
    return FoodRecognitionService(
        provider=provider or FakeProvider(),
        repository=InMemoryFoodRecognitionRepository(),
        object_storage=FakeStorage(),
        max_upload_bytes=max_upload_bytes,
    )


class TestFoodRecognitionSchemas:
    @pytest.mark.parametrize("filename, content_type", [("meal.jpg", "image/jpeg"), ("meal.png", "image/png")])
    @pytest.mark.asyncio
    async def test_valid_jpg_and_png_are_recognized(self, filename, content_type):
        service = make_service()

        result = await service.create_recognition(
            user_id=7,
            image=make_upload(filename, content_type),
            conf_threshold=0.5,
        )

        assert result.provider == "yolo"
        assert result.image_object_name.endswith(filename[-4:])
        assert [candidate.key for candidate in result.raw_detections] == ["tomato"]

    @pytest.mark.asyncio
    async def test_invalid_file_type_is_rejected(self):
        with pytest.raises(FoodRecognitionValidationError, match="JPG 或 PNG"):
            await make_service().create_recognition(
                user_id=7,
                image=make_upload("meal.gif", "image/gif"),
                conf_threshold=0.5,
            )

    @pytest.mark.asyncio
    async def test_oversized_file_is_rejected(self):
        with pytest.raises(FoodRecognitionValidationError, match="不能超过"):
            await make_service(max_upload_bytes=3).create_recognition(
                user_id=7,
                image=make_upload("meal.jpg", "image/jpeg", b"1234"),
                conf_threshold=0.5,
            )

    @pytest.mark.asyncio
    async def test_valid_and_invalid_conf_threshold(self):
        service = make_service()
        result = await service.create_recognition(
            user_id=7,
            image=make_upload("meal.jpg", "image/jpeg"),
            conf_threshold=0,
        )
        assert result.conf_threshold == 0

        with pytest.raises(FoodRecognitionValidationError, match="0 到 1"):
            await service.create_recognition(
                user_id=7,
                image=make_upload("meal.jpg", "image/jpeg"),
                conf_threshold=1.01,
            )

    def test_valid_and_invalid_bbox(self):
        assert BoundingBox(x1=1, y1=2, x2=3, y2=4).x2 == 3
        with pytest.raises(ValidationError, match="x2 > x1"):
            BoundingBox(x1=3, y1=2, x2=3, y2=4)
        with pytest.raises(ValidationError, match="y2 > y1"):
            BoundingBox(x1=1, y1=4, x2=3, y2=4)

    def test_duplicate_or_empty_confirmed_ingredients_are_rejected(self):
        ingredient = {"key": "tomato", "name": "番茄", "source": "yolo"}
        with pytest.raises(ValidationError, match="不能为空"):
            ConfirmIngredientsRequest(confirmed_ingredients=[])
        with pytest.raises(ValidationError, match="不允许重复"):
            ConfirmIngredientsRequest(confirmed_ingredients=[ingredient, ingredient])


class TestFoodRecognitionService:
    @pytest.mark.asyncio
    async def test_fake_provider_result_converts_to_response_and_can_be_confirmed(self):
        service = make_service()
        recognition = await service.create_recognition(
            user_id=7,
            image=make_upload("meal.jpg", "image/jpeg"),
            conf_threshold=0.5,
        )

        confirmed = await service.confirm_ingredients(
            user_id=7,
            recognition_id=recognition.recognition_id,
            confirmed_ingredients=[
                ConfirmedIngredient(key="tomato", name="番茄", quantity="2", unit="个", source="yolo"),
                ConfirmedIngredient(key="egg", name="鸡蛋", quantity="3", unit="个", source="manual"),
            ],
        )

        assert recognition.image_object_name.startswith("food-recognitions/7/")
        assert confirmed.status == "confirmed"
        assert [ingredient.key for ingredient in confirmed.confirmed_ingredients] == ["tomato", "egg"]
        assert confirmed.confirmed_at is not None


class TestFoodRecognitionApi:
    def test_all_food_routes_declare_authentication_dependency(self):
        food_routes = [route for route in router.routes if isinstance(route, APIRoute)]
        assert len(food_routes) == 3
        for route in food_routes:
            assert any(dependency.call is get_current_user for dependency in route.dependant.dependencies)

    def test_provider_error_maps_to_503(self):
        app = FastAPI()
        app.add_exception_handler(AppException, app_exception_handler)
        app.include_router(router)
        service = make_service(FailingProvider())

        async def override_current_user():
            return SimpleNamespace(id=7)

        app.dependency_overrides[get_current_user] = override_current_user
        app.dependency_overrides[get_food_recognition_service] = lambda: service

        with TestClient(app) as client:
            response = client.post(
                "/api/food/recognitions",
                data={"conf_threshold": "0.5"},
                files={"image": ("meal.jpg", b"image", "image/jpeg")},
            )

        assert response.status_code == 503
        assert response.json()["code"] == 503
        assert response.json()["message"] == "测试用 YOLO 不可用"
