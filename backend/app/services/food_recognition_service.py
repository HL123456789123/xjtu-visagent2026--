"""Food API 的同步识别、对象存储和持久化协调服务（V1）。"""

from __future__ import annotations

import asyncio
import tempfile
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Protocol

from fastapi import UploadFile

from app.core.exceptions import AppException
from app.entity.db_models import FoodRecognitionTask
from app.entity.food_schemas import (
    ConfirmIngredientsData,
    ConfirmedIngredient,
    FoodRecognitionCreateData,
    FoodRecognitionDetailData,
    IngredientCandidate,
    ModelDetection,
)
from app.repositories.food_repository import FoodRepository
from app.services.food_recognition_provider import (
    FoodModelUnavailableError,
    FoodRecognitionProvider,
    build_food_recognition_provider,
)

CHINA_TIMEZONE = timezone(timedelta(hours=8))


class FoodServiceError(AppException):
    """Food V1 中可预期错误的统一基类。"""


class FoodRecognitionNotFoundError(FoodServiceError):
    def __init__(self):
        super().__init__(404, "识别记录不存在", error_code="RECOGNITION_NOT_FOUND")


class FoodRecognitionAccessDeniedError(FoodServiceError):
    def __init__(self):
        super().__init__(403, "无权访问该识别记录", error_code="FORBIDDEN")


class ImageTooLargeError(FoodServiceError):
    def __init__(self):
        super().__init__(413, "图片超过 10 MB 限制", error_code="IMAGE_TOO_LARGE")


class UnsupportedImageTypeError(FoodServiceError):
    def __init__(self):
        super().__init__(415, "仅支持 JPG、JPEG、PNG 图片", error_code="UNSUPPORTED_IMAGE_TYPE")


class EmptyIngredientsError(FoodServiceError):
    def __init__(self):
        super().__init__(422, "食材不能为空", error_code="EMPTY_INGREDIENTS")


class FoodModelUnavailableServiceError(FoodServiceError):
    def __init__(self):
        super().__init__(503, "食物识别模型暂不可用", error_code="FOOD_MODEL_UNAVAILABLE")


class FoodStorageUnavailableError(FoodServiceError):
    def __init__(self):
        super().__init__(503, "图片存储服务暂不可用", error_code="INTERNAL_ERROR")


class FoodPersistenceError(FoodServiceError):
    def __init__(self):
        super().__init__(500, "识别记录保存失败", error_code="INTERNAL_ERROR")


class FoodObjectStorage(Protocol):
    def upload_file(self, object_name: str, file_path: str) -> str:
        """上传图片到对象存储。"""

    def delete_file(self, object_name: str) -> None:
        """删除补偿对象。"""

    def get_file(self, object_name: str) -> bytes:
        """读取原图字节。"""


def china_now() -> datetime:
    return datetime.now(CHINA_TIMEZONE)


def to_china_time(value: datetime) -> datetime:
    """SQLite 会丢失时区；对外响应始终按 V1 返回 +08:00。"""
    if value.tzinfo is None:
        return value.replace(tzinfo=CHINA_TIMEZONE)
    return value.astimezone(CHINA_TIMEZONE)


class FoodRecognitionService:
    """V1 Food 主流程：上传一张图、同步识别、保存候选项和确认快照。"""

    MAX_UPLOAD_BYTES = 10 * 1024 * 1024
    _MIME_TYPES_BY_EXTENSION = {
        ".jpg": {"image/jpeg", "image/jpg"},
        ".jpeg": {"image/jpeg", "image/jpg"},
        ".png": {"image/png"},
    }
    _IMAGE_HEADERS_BY_EXTENSION = {
        ".jpg": b"\xff\xd8\xff",
        ".jpeg": b"\xff\xd8\xff",
        ".png": b"\x89PNG\r\n\x1a\n",
    }

    def __init__(
        self,
        repository: FoodRepository,
        provider: FoodRecognitionProvider | None = None,
        object_storage: FoodObjectStorage | None = None,
    ):
        self.repository = repository
        self.provider = provider or build_food_recognition_provider()
        self._object_storage = object_storage

    async def create_recognition(
        self,
        *,
        user_id: int,
        image: UploadFile,
        conf_threshold: float,
    ) -> FoodRecognitionCreateData:
        content, extension = await self._read_and_validate_image(image)
        temp_path = self._create_temp_file(content, extension)
        object_name = self._build_object_name(user_id, extension)
        uploaded = False
        try:
            await self._upload_original(object_name, temp_path)
            uploaded = True
            detections = await self._recognize(temp_path, conf_threshold)
            candidates = self._convert_detections(detections)
            now = china_now()
            try:
                task = self.repository.create_recognition(
                    user_id=user_id,
                    image_object_name=object_name,
                    provider=self.provider.provider_name,
                    model_version=self.provider.model_version,
                    raw_detections=[item.model_dump(mode="json") for item in candidates],
                    created_at=now,
                )
            except Exception as exc:
                await self._delete_uploaded_object_quietly(object_name)
                uploaded = False
                raise FoodPersistenceError() from exc
            return self._to_create_data(task)
        except FoodServiceError:
            if uploaded:
                await self._delete_uploaded_object_quietly(object_name)
            raise
        finally:
            self._remove_temp_file(temp_path)

    def get_recognition(self, *, user_id: int, recognition_id: int) -> FoodRecognitionDetailData:
        task = self.repository.get_recognition(recognition_id)
        self._assert_owned(task, user_id)
        return self._to_detail_data(task)

    def confirm_ingredients(
        self,
        *,
        user_id: int,
        recognition_id: int,
        ingredients: list[ConfirmedIngredient],
    ) -> ConfirmIngredientsData:
        if not ingredients:
            raise EmptyIngredientsError()
        self._assert_owned(self.repository.get_recognition(recognition_id), user_id)
        confirmed_at = china_now()
        task = self.repository.replace_confirmed_ingredients(
            recognition_id,
            user_id,
            [item.model_dump(mode="json") for item in ingredients],
            confirmed_at,
        )
        if task is None:
            # 已先完成存在性与归属检查；这里代表并发删除，按不存在处理。
            raise FoodRecognitionNotFoundError()
        return ConfirmIngredientsData(
            recognition_id=task.id,
            confirmed_ingredients=[
                ConfirmedIngredient.model_validate(item)
                for item in (task.confirmed_ingredients or [])
            ],
            confirmed_at=to_china_time(task.updated_at),
        )

    async def get_image(self, *, user_id: int, recognition_id: int) -> tuple[bytes, str]:
        """按用户隔离读取原图，使 V1 ``image_url`` 可实际访问。"""
        task = self.repository.get_recognition(recognition_id)
        self._assert_owned(task, user_id)
        try:
            content = await asyncio.to_thread(
                self._get_object_storage().get_file, task.image_object_name
            )
        except Exception as exc:
            raise FoodStorageUnavailableError() from exc
        suffix = Path(task.image_object_name).suffix.lower()
        media_type = "image/png" if suffix == ".png" else "image/jpeg"
        return content, media_type

    async def _recognize(self, temp_path: str, conf_threshold: float) -> list[ModelDetection]:
        try:
            return await asyncio.to_thread(self.provider.recognize, temp_path, conf_threshold)
        except FoodModelUnavailableError as exc:
            raise FoodModelUnavailableServiceError() from exc
        except Exception as exc:
            raise FoodModelUnavailableServiceError() from exc

    def _convert_detections(self, detections: list[ModelDetection]) -> list[IngredientCandidate]:
        candidates: list[IngredientCandidate] = []
        for index, detection in enumerate(detections, start=1):
            candidates.append(
                IngredientCandidate(
                    candidate_id=f"det-{index}",
                    class_name=detection.class_name,
                    display_name=self.provider.get_display_name(detection.class_name),
                    confidence=detection.confidence,
                    bbox=detection.bbox,
                    source="model",
                )
            )
        return candidates

    async def _read_and_validate_image(self, image: UploadFile) -> tuple[bytes, str]:
        filename = image.filename or ""
        extension = Path(filename).suffix.lower()
        allowed_mime_types = self._MIME_TYPES_BY_EXTENSION.get(extension)
        declared_mime = (image.content_type or "").split(";", maxsplit=1)[0].lower()
        if allowed_mime_types is None or declared_mime not in allowed_mime_types:
            raise UnsupportedImageTypeError()

        content = await image.read(self.MAX_UPLOAD_BYTES + 1)
        if len(content) > self.MAX_UPLOAD_BYTES:
            raise ImageTooLargeError()
        if not content or not content.startswith(self._IMAGE_HEADERS_BY_EXTENSION[extension]):
            raise UnsupportedImageTypeError()
        return content, extension

    @staticmethod
    def _create_temp_file(content: bytes, extension: str) -> str:
        path = Path(tempfile.gettempdir()) / f"food-recognition-{uuid.uuid4()}{extension}"
        with path.open("xb") as output:
            output.write(content)
        return str(path.resolve())

    @staticmethod
    def _build_object_name(user_id: int, extension: str) -> str:
        now = china_now()
        return f"food/{user_id}/{now:%Y/%m/%d}/{uuid.uuid4()}{extension}"

    async def _upload_original(self, object_name: str, temp_path: str) -> None:
        try:
            await asyncio.to_thread(self._get_object_storage().upload_file, object_name, temp_path)
        except Exception as exc:
            raise FoodStorageUnavailableError() from exc

    async def _delete_uploaded_object_quietly(self, object_name: str) -> None:
        try:
            await asyncio.to_thread(self._get_object_storage().delete_file, object_name)
        except Exception:
            # 补偿失败不掩盖原本的业务错误，日志由对象存储侧与调用方补充。
            return

    def _get_object_storage(self) -> FoodObjectStorage:
        if self._object_storage is None:
            try:
                from app.storage.minio_client import MinIOClient

                self._object_storage = MinIOClient()
            except Exception as exc:
                raise FoodStorageUnavailableError() from exc
        return self._object_storage

    @staticmethod
    def _remove_temp_file(temp_path: str) -> None:
        Path(temp_path).unlink(missing_ok=True)

    @staticmethod
    def _assert_owned(task: FoodRecognitionTask | None, user_id: int) -> None:
        if task is None:
            raise FoodRecognitionNotFoundError()
        if task.user_id != user_id:
            raise FoodRecognitionAccessDeniedError()

    @staticmethod
    def _image_url(task: FoodRecognitionTask) -> str:
        return f"/api/files/food/{task.id}"

    def _to_create_data(self, task: FoodRecognitionTask) -> FoodRecognitionCreateData:
        return FoodRecognitionCreateData(
            recognition_id=task.id,
            status="completed",
            provider=task.provider,
            model_version=task.model_version,
            image_url=self._image_url(task),
            ingredients=[
                IngredientCandidate.model_validate(item) for item in (task.raw_detections or [])
            ],
            created_at=to_china_time(task.created_at),
        )

    def _to_detail_data(self, task: FoodRecognitionTask) -> FoodRecognitionDetailData:
        return FoodRecognitionDetailData(
            **self._to_create_data(task).model_dump(),
            confirmed_ingredients=[
                ConfirmedIngredient.model_validate(item)
                for item in (task.confirmed_ingredients or [])
            ],
            updated_at=to_china_time(task.updated_at),
        )
