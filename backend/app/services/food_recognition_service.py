"""食物识别的上传、识别、确认快照服务骨架。"""
import asyncio
import tempfile
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Protocol

from fastapi import UploadFile
from pydantic import ValidationError

from app.core.exceptions import AppException
from app.entity.food_schemas import (
    ConfirmedIngredient,
    FoodRecognitionResponse,
    IngredientCandidate,
)
from app.services.food_recognition_provider import (
    FoodRecognitionInferenceError,
    FoodRecognitionInvalidResultError,
    FoodRecognitionProvider,
    FoodRecognitionProviderError,
    YoloFoodRecognitionProvider,
)


class FoodRecognitionValidationError(AppException):
    """上传文件或服务参数不符合契约。"""

    def __init__(self, message: str, detail: str | None = None):
        super().__init__(code=422, message=message, detail=detail)


class FoodRecognitionStorageError(AppException):
    """MinIO 上传或访问出现异常。"""

    def __init__(self, message: str = "食物图片存储服务不可用", detail: str | None = None):
        super().__init__(code=503, message=message, detail=detail)


class FoodRecognitionNotFoundError(AppException):
    """识别任务不存在。"""

    def __init__(self, recognition_id: str):
        super().__init__(code=404, message="食物识别任务不存在", detail=recognition_id)


class FoodRecognitionAccessDeniedError(AppException):
    """当前用户不拥有目标识别任务。"""

    def __init__(self, recognition_id: str):
        super().__init__(code=403, message="无权访问该食物识别任务", detail=recognition_id)


class FoodObjectStorage(Protocol):
    """服务需要的最小对象存储接口。"""

    def upload_file(self, object_name: str, file_path: str) -> str:
        """上传文件；返回值可为预签名 URL，服务不会向客户端暴露它。"""


@dataclass
class FoodRecognitionRecord:
    """持久化层所需的识别任务数据，不是 ORM 模型。"""

    user_id: int
    recognition: FoodRecognitionResponse
    image_mime_type: str
    image_size: int


class FoodRecognitionRepository(Protocol):
    """待 ORM 接入的可注入 Repository 契约。"""

    async def create(self, record: FoodRecognitionRecord) -> FoodRecognitionRecord:
        """创建识别任务。"""

    async def get(self, recognition_id: str) -> FoodRecognitionRecord | None:
        """按任务 ID 查询。"""

    async def update(self, record: FoodRecognitionRecord) -> FoodRecognitionRecord | None:
        """用完整快照更新识别任务。"""


class InMemoryFoodRecognitionRepository:
    """仅供 Day 1 API 骨架运行和单元测试使用的临时 Repository。

    它不是 Provider，也不参与任何生产 Mock 模式；Day 2 应以数据库 Repository
    注入替换，并保持 ``FoodRecognitionRepository`` 契约不变。
    """

    def __init__(self):
        self._records: dict[str, FoodRecognitionRecord] = {}

    async def create(self, record: FoodRecognitionRecord) -> FoodRecognitionRecord:
        stored = self._copy_record(record)
        self._records[stored.recognition.recognition_id] = stored
        return self._copy_record(stored)

    async def get(self, recognition_id: str) -> FoodRecognitionRecord | None:
        record = self._records.get(recognition_id)
        return self._copy_record(record) if record else None

    async def update(self, record: FoodRecognitionRecord) -> FoodRecognitionRecord | None:
        recognition_id = record.recognition.recognition_id
        if recognition_id not in self._records:
            return None
        stored = self._copy_record(record)
        self._records[recognition_id] = stored
        return self._copy_record(stored)

    @staticmethod
    def _copy_record(record: FoodRecognitionRecord) -> FoodRecognitionRecord:
        return FoodRecognitionRecord(
            user_id=record.user_id,
            recognition=record.recognition.model_copy(deep=True),
            image_mime_type=record.image_mime_type,
            image_size=record.image_size,
        )


class FoodRecognitionService:
    """协调上传、对象存储、YOLO Provider 与识别快照。"""

    MAX_UPLOAD_BYTES = 10 * 1024 * 1024
    _MIME_TYPES_BY_EXTENSION = {
        ".jpg": {"image/jpeg", "image/jpg"},
        ".jpeg": {"image/jpeg", "image/jpg"},
        ".png": {"image/png"},
    }

    def __init__(
        self,
        provider: FoodRecognitionProvider | None = None,
        repository: FoodRecognitionRepository | None = None,
        object_storage: FoodObjectStorage | None = None,
        max_upload_bytes: int | None = None,
    ):
        self.provider = provider or YoloFoodRecognitionProvider()
        self.repository = repository or InMemoryFoodRecognitionRepository()
        self._object_storage = object_storage
        self.max_upload_bytes = max_upload_bytes or self.MAX_UPLOAD_BYTES

    async def create_recognition(
        self,
        *,
        user_id: int,
        image: UploadFile,
        conf_threshold: float,
    ) -> FoodRecognitionResponse:
        """创建一张图片对应的一条食物识别任务。"""
        self._validate_conf_threshold(conf_threshold)
        content, extension, mime_type = await self._read_and_validate_image(image)
        temp_path = self._create_temp_file(content, extension)

        try:
            recognition_id = str(uuid.uuid4())
            object_name = f"food-recognitions/{user_id}/{recognition_id}{extension}"
            await self._upload_original(object_name, temp_path)
            candidates = await self._recognize(temp_path, conf_threshold)
            now = datetime.now()
            recognition = FoodRecognitionResponse(
                recognition_id=recognition_id,
                status="recognized",
                image_object_name=object_name,
                model_version=self.provider.model_version,
                conf_threshold=conf_threshold,
                raw_detections=candidates,
                created_at=now,
                updated_at=now,
            )
            record = FoodRecognitionRecord(
                user_id=user_id,
                recognition=recognition,
                image_mime_type=mime_type,
                image_size=len(content),
            )
            stored = await self.repository.create(record)
            return stored.recognition
        finally:
            self._remove_temp_file(temp_path)

    async def get_recognition(self, *, user_id: int, recognition_id: str) -> FoodRecognitionResponse:
        """查询当前用户拥有的食物识别任务。"""
        record = await self._get_owned_record(user_id, recognition_id)
        return record.recognition

    async def confirm_ingredients(
        self,
        *,
        user_id: int,
        recognition_id: str,
        confirmed_ingredients: list[ConfirmedIngredient],
    ) -> FoodRecognitionResponse:
        """用用户提交的完整列表覆盖确认食材快照。"""
        if not confirmed_ingredients:
            raise FoodRecognitionValidationError("确认食材列表不能为空")

        keys = [ingredient.key for ingredient in confirmed_ingredients]
        if len(keys) != len(set(keys)):
            raise FoodRecognitionValidationError("食材 key 不允许重复")

        record = await self._get_owned_record(user_id, recognition_id)
        now = datetime.now()
        updated_recognition = record.recognition.model_copy(
            update={
                "status": "confirmed",
                "confirmed_ingredients": confirmed_ingredients,
                "confirmed_at": now,
                "updated_at": now,
            },
            deep=True,
        )
        updated = await self.repository.update(
            FoodRecognitionRecord(
                user_id=record.user_id,
                recognition=updated_recognition,
                image_mime_type=record.image_mime_type,
                image_size=record.image_size,
            )
        )
        if updated is None:
            raise FoodRecognitionNotFoundError(recognition_id)
        return updated.recognition

    def _validate_conf_threshold(self, conf_threshold: float) -> None:
        if not 0 <= conf_threshold <= 1:
            raise FoodRecognitionValidationError("置信度阈值必须位于 0 到 1 之间")

    async def _read_and_validate_image(self, image: UploadFile) -> tuple[bytes, str, str]:
        filename = image.filename or ""
        extension = Path(filename).suffix.lower()
        allowed_mime_types = self._MIME_TYPES_BY_EXTENSION.get(extension)
        if not allowed_mime_types:
            raise FoodRecognitionValidationError("仅支持上传一张 JPG 或 PNG 图片")

        declared_mime_type = (image.content_type or "").split(";", maxsplit=1)[0].lower()
        if declared_mime_type and declared_mime_type not in allowed_mime_types:
            raise FoodRecognitionValidationError("文件扩展名与 MIME 类型不匹配")

        content = await image.read(self.max_upload_bytes + 1)
        if not content:
            raise FoodRecognitionValidationError("上传图片不能为空")
        if len(content) > self.max_upload_bytes:
            raise FoodRecognitionValidationError(
                f"图片大小不能超过 {self.max_upload_bytes // (1024 * 1024)} MB"
            )

        mime_type = declared_mime_type or sorted(allowed_mime_types)[0]
        return content, extension, mime_type

    @staticmethod
    def _create_temp_file(content: bytes, extension: str) -> str:
        with tempfile.NamedTemporaryFile(mode="wb", suffix=extension, delete=False) as temp_file:
            temp_file.write(content)
            return temp_file.name

    async def _upload_original(self, object_name: str, temp_path: str) -> None:
        storage = self._get_object_storage()
        try:
            await asyncio.to_thread(storage.upload_file, object_name, temp_path)
        except FoodRecognitionStorageError:
            raise
        except Exception as exc:
            raise FoodRecognitionStorageError(detail=str(exc)) from exc

    def _get_object_storage(self) -> FoodObjectStorage:
        if self._object_storage is None:
            try:
                from app.storage.minio_client import MinIOClient

                self._object_storage = MinIOClient()
            except Exception as exc:
                raise FoodRecognitionStorageError(detail=str(exc)) from exc
        return self._object_storage

    async def _recognize(self, temp_path: str, conf_threshold: float) -> list[IngredientCandidate]:
        try:
            raw_candidates = await self.provider.recognize(temp_path, conf_threshold)
        except FoodRecognitionProviderError:
            raise
        except Exception as exc:
            raise FoodRecognitionInferenceError(detail=str(exc)) from exc

        if not isinstance(raw_candidates, list):
            raise FoodRecognitionInvalidResultError("YOLO 返回了非列表格式的识别结果")

        try:
            candidates = [IngredientCandidate.model_validate(candidate) for candidate in raw_candidates]
        except (TypeError, ValidationError) as exc:
            raise FoodRecognitionInvalidResultError("YOLO 返回的识别结果不符合契约", str(exc)) from exc

        return self._normalize_candidates(candidates, conf_threshold)

    @staticmethod
    def _normalize_candidates(
        candidates: list[IngredientCandidate],
        conf_threshold: float,
    ) -> list[IngredientCandidate]:
        """过滤阈值以下结果，并为相同食材 key 保留最高置信度项。"""
        ordered = sorted(
            (candidate for candidate in candidates if candidate.confidence >= conf_threshold),
            key=lambda candidate: candidate.confidence,
            reverse=True,
        )
        unique_candidates: list[IngredientCandidate] = []
        seen_keys: set[str] = set()
        for candidate in ordered:
            if candidate.key not in seen_keys:
                unique_candidates.append(candidate)
                seen_keys.add(candidate.key)
        return unique_candidates

    async def _get_owned_record(
        self,
        user_id: int,
        recognition_id: str,
    ) -> FoodRecognitionRecord:
        record = await self.repository.get(recognition_id)
        if record is None:
            raise FoodRecognitionNotFoundError(recognition_id)
        if record.user_id != user_id:
            raise FoodRecognitionAccessDeniedError(recognition_id)
        return record

    @staticmethod
    def _remove_temp_file(temp_path: str) -> None:
        try:
            Path(temp_path).unlink(missing_ok=True)
        except OSError:
            # 临时文件无法清理不应掩盖原始业务异常；交给系统临时目录策略后续处理。
            pass


food_recognition_service = FoodRecognitionService()
