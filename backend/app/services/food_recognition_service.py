"""V1.1 Food orchestration: validate a batch, call a single-image provider, persist once."""

from __future__ import annotations

import asyncio
import tempfile
import uuid
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from io import BytesIO
from pathlib import Path
from typing import Mapping, Protocol

import yaml
from fastapi import UploadFile
from PIL import Image, UnidentifiedImageError

from app.config.settings import Settings
from app.core.exceptions import AppException
from app.entity.db_models import FoodRecognitionTask
from app.entity.food_schemas import (
    ConfirmIngredientsData,
    ConfirmedIngredient,
    FoodRecognitionCreateData,
    FoodRecognitionDetailData,
    IngredientCandidate,
    RecognitionImage,
)
from app.modeling.food_yolo_runtime import (
    FoodModelUnavailableError,
    FoodRecognitionProvider,
    ModelDetection,
    YoloFoodRecognitionProvider,
)
from app.repositories.food_repository import FoodRepository

CST = timezone(timedelta(hours=8))


class FoodServiceError(AppException):
    def __init__(self, status_code: int, error_code: str, message: str) -> None:
        super().__init__(status_code, message, detail=error_code)
        self.error_code = error_code


class InvalidImageCountError(FoodServiceError):
    def __init__(self) -> None:
        super().__init__(400, "INVALID_IMAGE_COUNT", "图片数量必须为 1 至 5 张")


class ImageTooLargeError(FoodServiceError):
    def __init__(self) -> None:
        super().__init__(413, "IMAGE_TOO_LARGE", "单张图片不得超过 10 MB")


class ImageBatchTooLargeError(FoodServiceError):
    def __init__(self) -> None:
        super().__init__(413, "IMAGE_BATCH_TOO_LARGE", "整批图片不得超过 50 MB")


class UnsupportedImageTypeError(FoodServiceError):
    def __init__(self) -> None:
        super().__init__(415, "UNSUPPORTED_IMAGE_TYPE", "仅支持 JPG、JPEG、PNG 图片")


class InvalidImageContentError(FoodServiceError):
    def __init__(self) -> None:
        super().__init__(422, "INVALID_IMAGE_CONTENT", "图片内容无法解码")


class EmptyIngredientsError(FoodServiceError):
    def __init__(self) -> None:
        super().__init__(422, "EMPTY_INGREDIENTS", "食材不能为空")


class FoodRecognitionNotFoundError(FoodServiceError):
    def __init__(self) -> None:
        super().__init__(404, "RECOGNITION_NOT_FOUND", "识别记录不存在")


class FoodRecognitionAccessDeniedError(FoodServiceError):
    def __init__(self) -> None:
        super().__init__(403, "FORBIDDEN", "无权访问该识别记录")


class InvalidImageIndexError(FoodServiceError):
    def __init__(self) -> None:
        super().__init__(400, "BAD_REQUEST", "图片序号不存在")


class FoodModelUnavailableServiceError(FoodServiceError):
    def __init__(self) -> None:
        super().__init__(503, "FOOD_MODEL_UNAVAILABLE", "食物识别模型暂不可用")


class FoodStorageUnavailableError(FoodServiceError):
    def __init__(self) -> None:
        super().__init__(500, "INTERNAL_ERROR", "图片存储失败")


class FoodPersistenceError(FoodServiceError):
    def __init__(self) -> None:
        super().__init__(500, "INTERNAL_ERROR", "识别记录保存失败")


class FoodObjectStorage(Protocol):
    def upload_file(self, object_name: str, file_path: str) -> str: ...
    def delete_file(self, object_name: str) -> None: ...
    def get_file(self, object_name: str) -> bytes: ...


class MinioFoodObjectStorage:
    """Small adapter over the existing MinIO client without changing its shared module."""

    def __init__(self) -> None:
        from app.storage.minio_client import get_minio_client

        self._client = get_minio_client()

    def upload_file(self, object_name: str, file_path: str) -> str:
        return self._client.upload_file(object_name, file_path)

    def delete_file(self, object_name: str) -> None:
        self._client.delete_file(object_name)

    def get_file(self, object_name: str) -> bytes:
        response = self._client.client.get_object(self._client.bucket_name, object_name)
        try:
            return response.read()
        finally:
            response.close()
            response.release_conn()


class MockFoodRecognitionProvider:
    def recognize(
        self, image_path: str, conf_threshold: float = 0.25
    ) -> list[ModelDetection]:
        del image_path, conf_threshold
        return []


class UnavailableFoodRecognitionProvider:
    def __init__(self, error: FoodModelUnavailableError) -> None:
        self._error = error

    def recognize(
        self, image_path: str, conf_threshold: float = 0.25
    ) -> list[ModelDetection]:
        del image_path, conf_threshold
        raise self._error


def _read_display_names(classes_path: Path) -> dict[str, str]:
    payload = yaml.safe_load(classes_path.read_text(encoding="utf-8")) or {}
    names = payload.get("names", {})
    if not isinstance(names, dict):
        raise ValueError("invalid classes mapping")
    result: dict[str, str] = {}
    for definition in names.values():
        if not isinstance(definition, dict):
            raise ValueError("invalid class definition")
        result[str(definition["class_name"])] = str(definition["display_name"])
    return result


@lru_cache(maxsize=1)
def build_default_food_provider() -> tuple[FoodRecognitionProvider, str, str, dict[str, str]]:
    runtime_settings = Settings()
    mode = runtime_settings.FOOD_PROVIDER
    if mode == "mock":
        return MockFoodRecognitionProvider(), "mock", "food-mock-v1", {}
    if mode != "yolo":
        error = FoodModelUnavailableError(f"unsupported FOOD_PROVIDER: {mode}")
        return UnavailableFoodRecognitionProvider(error), "yolo", "food-yolo-v1", {}

    backend_dir = Path(__file__).resolve().parents[2]
    model_path = runtime_settings.FOOD_MODEL_PATH
    classes_path = runtime_settings.FOOD_CLASSES_PATH or str(
        backend_dir / "scripts" / "food_model" / "classes.yaml"
    )
    try:
        display_names = _read_display_names(Path(classes_path))
        provider = YoloFoodRecognitionProvider(model_path, classes_path)
    except (FoodModelUnavailableError, OSError, KeyError, TypeError, ValueError, yaml.YAMLError) as exc:
        error = (
            exc
            if isinstance(exc, FoodModelUnavailableError)
            else FoodModelUnavailableError("food classes are unavailable")
        )
        return UnavailableFoodRecognitionProvider(error), "yolo", "food-yolo-v1", {}
    return provider, "yolo", "food-yolo-v1", display_names


def china_now() -> datetime:
    return datetime.now(CST)


def to_china_time(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=CST)
    return value.astimezone(CST)


class FoodRecognitionService:
    MIN_IMAGES = 1
    MAX_IMAGES = 5
    MAX_SINGLE_IMAGE_BYTES = 10 * 1024 * 1024
    MAX_BATCH_BYTES = 50 * 1024 * 1024
    _MIME_TYPES = {
        ".jpg": {"image/jpeg", "image/jpg"},
        ".jpeg": {"image/jpeg", "image/jpg"},
        ".png": {"image/png"},
    }
    _PIL_FORMATS = {".jpg": "JPEG", ".jpeg": "JPEG", ".png": "PNG"}

    def __init__(
        self,
        repository: FoodRepository,
        provider: FoodRecognitionProvider | None = None,
        object_storage: FoodObjectStorage | None = None,
        *,
        provider_name: str | None = None,
        model_version: str | None = None,
        display_names: Mapping[str, str] | None = None,
    ) -> None:
        if provider is None:
            provider, default_name, default_version, default_names = build_default_food_provider()
            provider_name = provider_name or default_name
            model_version = model_version or default_version
            display_names = display_names if display_names is not None else default_names
        self.repository = repository
        self.provider = provider
        self.provider_name = provider_name or "yolo"
        self.model_version = model_version or "food-yolo-v1"
        self.display_names = dict(display_names or {})
        self._object_storage = object_storage

    async def create_recognition(
        self,
        *,
        user_id: int,
        images: list[UploadFile],
        conf_threshold: float,
    ) -> FoodRecognitionCreateData:
        self._validate_image_count(len(images))
        validated = [await self._read_image(upload) for upload in images]
        self._validate_batch_sizes([len(content) for content, _ in validated])
        for content, extension in validated:
            self._validate_decoded_image(content, extension)

        temp_images: list[tuple[str, str]] = []
        uploaded_names: list[str] = []
        task: FoodRecognitionTask | None = None
        try:
            temp_images = [
                (self._create_temp_file(content, extension), extension)
                for content, extension in validated
            ]
            object_names = [
                self._build_object_name(user_id, extension) for _, extension in temp_images
            ]
            for object_name, (temp_path, _) in zip(object_names, temp_images, strict=True):
                await self._upload_original(object_name, temp_path)
                uploaded_names.append(object_name)

            detections_by_image = [
                await self._recognize(temp_path, conf_threshold) for temp_path, _ in temp_images
            ]
            raw_detections = self._group_raw_detections(object_names, detections_by_image)
            created_at = china_now()
            try:
                task = self.repository.create_recognition(
                    user_id=user_id,
                    image_object_names=object_names,
                    status="completed",
                    provider=self.provider_name,
                    model_version=self.model_version,
                    created_at=created_at,
                )
                task = self.repository.save_raw_detections(task.id, raw_detections)
                if task is None:
                    raise RuntimeError("recognition disappeared while saving detections")
            except Exception as exc:
                if task is not None:
                    try:
                        self.repository.delete_recognition(task.id)
                    except Exception:
                        pass
                raise FoodPersistenceError() from exc
            return self._to_create_data(task)
        except FoodServiceError:
            for object_name in uploaded_names:
                await self._delete_uploaded_object_quietly(object_name)
            raise
        finally:
            for temp_path, _ in temp_images:
                Path(temp_path).unlink(missing_ok=True)

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
            raise FoodRecognitionNotFoundError()
        return ConfirmIngredientsData(
            recognition_id=task.id,
            confirmed_ingredients=[
                ConfirmedIngredient.model_validate(item)
                for item in (task.confirmed_ingredients or [])
            ],
            confirmed_at=to_china_time(task.updated_at),
        )

    async def get_image(
        self, *, user_id: int, recognition_id: int, image_index: int
    ) -> tuple[bytes, str]:
        task = self.repository.get_recognition(recognition_id)
        self._assert_owned(task, user_id)
        object_names = list(task.image_object_names or [])
        if image_index < 0 or image_index >= len(object_names):
            raise InvalidImageIndexError()
        object_name = object_names[image_index]
        try:
            content = await asyncio.to_thread(self._get_storage().get_file, object_name)
        except Exception as exc:
            raise FoodStorageUnavailableError() from exc
        media_type = "image/png" if Path(object_name).suffix.lower() == ".png" else "image/jpeg"
        return content, media_type

    @classmethod
    def _validate_image_count(cls, count: int) -> None:
        if count < cls.MIN_IMAGES or count > cls.MAX_IMAGES:
            raise InvalidImageCountError()

    @classmethod
    def _validate_batch_sizes(cls, sizes: list[int]) -> None:
        if any(size > cls.MAX_SINGLE_IMAGE_BYTES for size in sizes):
            raise ImageTooLargeError()
        if sum(sizes) > cls.MAX_BATCH_BYTES:
            raise ImageBatchTooLargeError()

    async def _read_image(self, upload: UploadFile) -> tuple[bytes, str]:
        extension = Path(upload.filename or "").suffix.lower()
        declared_type = (upload.content_type or "").split(";", maxsplit=1)[0].lower()
        if extension not in self._MIME_TYPES or declared_type not in self._MIME_TYPES[extension]:
            raise UnsupportedImageTypeError()
        content = await upload.read(self.MAX_SINGLE_IMAGE_BYTES + 1)
        return content, extension

    @classmethod
    def _validate_decoded_image(cls, content: bytes, extension: str) -> None:
        if not content:
            raise InvalidImageContentError()
        try:
            with Image.open(BytesIO(content)) as image:
                actual_format = image.format
                image.verify()
            # verify() checks container integrity, while load() forces pixel decoding.
            # Reopen because Pillow invalidates the image object after verify().
            with Image.open(BytesIO(content)) as image:
                image.load()
        except (OSError, UnidentifiedImageError, SyntaxError, ValueError) as exc:
            raise InvalidImageContentError() from exc
        if actual_format != cls._PIL_FORMATS[extension]:
            raise InvalidImageContentError()

    async def _recognize(
        self, temp_path: str, conf_threshold: float
    ) -> list[ModelDetection]:
        try:
            return await asyncio.to_thread(self.provider.recognize, temp_path, conf_threshold)
        except Exception as exc:
            raise FoodModelUnavailableServiceError() from exc

    @staticmethod
    def _group_raw_detections(
        object_names: list[str], detections_by_image: list[list[ModelDetection]]
    ) -> list[dict[str, object]]:
        return [
            {
                "image_index": image_index,
                "image_object_name": object_name,
                "detections": [asdict(detection) for detection in detections],
            }
            for image_index, (object_name, detections) in enumerate(
                zip(object_names, detections_by_image, strict=True)
            )
        ]

    def _candidates_from_raw(
        self, raw_detections: list[dict[str, object]]
    ) -> list[IngredientCandidate]:
        candidates: list[IngredientCandidate] = []
        for group in raw_detections:
            image_index = int(group["image_index"])
            detections = group.get("detections", [])
            for detection_index, raw_detection in enumerate(detections, start=1):
                detection = ModelDetection(
                    class_name=str(raw_detection["class_name"]),
                    confidence=float(raw_detection["confidence"]),
                    bbox=self._bbox_from_raw(raw_detection["bbox"]),
                )
                candidates.append(
                    IngredientCandidate(
                        candidate_id=f"img-{image_index}-det-{detection_index}",
                        image_index=image_index,
                        class_name=detection.class_name,
                        display_name=self.display_names.get(
                            detection.class_name, detection.class_name
                        ),
                        confidence=detection.confidence,
                        bbox=asdict(detection.bbox),
                        source="model",
                    )
                )
        return candidates

    @staticmethod
    def _bbox_from_raw(raw_bbox: object):
        from app.modeling.food_yolo_runtime import BoundingBox

        if not isinstance(raw_bbox, dict):
            raise ValueError("invalid stored bbox")
        return BoundingBox(
            x1=float(raw_bbox["x1"]),
            y1=float(raw_bbox["y1"]),
            x2=float(raw_bbox["x2"]),
            y2=float(raw_bbox["y2"]),
        )

    @staticmethod
    def _image_url(recognition_id: int, image_index: int) -> str:
        return f"/api/files/food/{recognition_id}/{image_index}"

    def _to_create_data(self, task: FoodRecognitionTask) -> FoodRecognitionCreateData:
        object_names = list(task.image_object_names or [])
        return FoodRecognitionCreateData(
            recognition_id=task.id,
            status="completed",
            provider=task.provider,
            model_version=task.model_version,
            images=[
                RecognitionImage(
                    image_index=index,
                    image_url=self._image_url(task.id, index),
                )
                for index in range(len(object_names))
            ],
            ingredients=self._candidates_from_raw(task.raw_detections or []),
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

    @staticmethod
    def _assert_owned(task: FoodRecognitionTask | None, user_id: int) -> None:
        if task is None:
            raise FoodRecognitionNotFoundError()
        if task.user_id != user_id:
            raise FoodRecognitionAccessDeniedError()

    @staticmethod
    def _create_temp_file(content: bytes, extension: str) -> str:
        path = Path(tempfile.gettempdir()) / f"food-recognition-{uuid.uuid4()}{extension}"
        with path.open("xb") as output:
            output.write(content)
        return str(path.resolve())

    @staticmethod
    def _build_object_name(user_id: int, extension: str) -> str:
        return f"food/{user_id}/{china_now():%Y/%m/%d}/{uuid.uuid4()}{extension}"

    async def _upload_original(self, object_name: str, temp_path: str) -> None:
        try:
            await asyncio.to_thread(self._get_storage().upload_file, object_name, temp_path)
        except Exception as exc:
            raise FoodStorageUnavailableError() from exc

    async def _delete_uploaded_object_quietly(self, object_name: str) -> None:
        try:
            await asyncio.to_thread(self._get_storage().delete_file, object_name)
        except Exception:
            return

    def _get_storage(self) -> FoodObjectStorage:
        if self._object_storage is None:
            self._object_storage = MinioFoodObjectStorage()
        return self._object_storage
