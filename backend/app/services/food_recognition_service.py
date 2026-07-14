"""食物识别的上传、识别、确认快照服务骨架。"""

import asyncio
import tempfile
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Protocol

from fastapi import UploadFile
from pydantic import ValidationError

from app.core.exceptions import AppException
from app.core.logger import get_logger
from app.entity.food_schemas import (
    ConfirmedIngredient,
    FoodRecognitionResponse,
    IngredientCandidate,
)
from app.services.food_recognition_provider import (
    FOOD_LABEL_NAMES,
    FoodRecognitionInferenceError,
    FoodRecognitionInvalidResultError,
    FoodRecognitionProvider,
    FoodRecognitionProviderError,
    YoloFoodRecognitionProvider,
)

logger = get_logger("food_recognition_service")


class FoodRecognitionValidationError(AppException):
    """上传文件或服务参数不符合契约。"""

    def __init__(self, message: str, detail: str | None = None):
        super().__init__(code=422, message=message, detail=detail)


class FoodRecognitionStorageError(AppException):
    """MinIO 上传或访问出现异常。"""

    def __init__(self, message: str = "食物图片存储服务不可用", detail: str | None = None):
        super().__init__(code=503, message=message, detail=detail)


class FoodRecognitionPersistenceError(AppException):
    """食物识别任务无法被可靠持久化。"""

    def __init__(self, message: str = "食物识别任务持久化失败", detail: str | None = None):
        super().__init__(code=503, message=message, detail=detail)


class FoodRecognitionStateError(FoodRecognitionValidationError):
    """识别任务当前状态不允许执行目标操作。"""


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

    def delete_file(self, object_name: str) -> None:
        """在数据库持久化失败时删除已上传的对象。"""


@dataclass
class FoodRecognitionRecord:
    """持久化层所需的识别任务数据，不是 ORM 模型。"""

    user_id: int
    recognition: FoodRecognitionResponse
    image_mime_type: str
    image_size: int
    error_message: str | None = None

    def as_persistence_payload(self) -> dict[str, Any]:
        """提供给 ORM Repository 的 JSON 安全字段，绝不包含本地临时文件路径。"""
        recognition = self.recognition.model_dump(mode="json")
        return {
            "id": recognition["recognition_id"],
            "user_id": self.user_id,
            "image_object_name": recognition["image_object_name"],
            "image_mime_type": self.image_mime_type,
            "image_size": self.image_size,
            "provider": recognition["provider"],
            "model_version": recognition["model_version"],
            "conf_threshold": recognition["conf_threshold"],
            "status": recognition["status"],
            "raw_detections": recognition["raw_detections"],
            "confirmed_ingredients": recognition["confirmed_ingredients"],
            "error_message": self.error_message,
            "confirmed_at": recognition["confirmed_at"],
            "created_at": recognition["created_at"],
            "updated_at": recognition["updated_at"],
        }


class FoodRecognitionRepository(Protocol):
    """待 ORM 接入的可注入 Repository 契约。"""

    async def create(self, record: FoodRecognitionRecord) -> FoodRecognitionRecord:
        """创建识别任务。"""

    async def get(self, recognition_id: str) -> FoodRecognitionRecord | None:
        """按任务 ID 查询。"""

    async def update(self, record: FoodRecognitionRecord) -> FoodRecognitionRecord | None:
        """用完整快照更新识别任务。"""


class FoodRecognitionService:
    """协调上传、对象存储、YOLO Provider 与识别快照。"""

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
        provider: FoodRecognitionProvider | None = None,
        repository: FoodRecognitionRepository | None = None,
        object_storage: FoodObjectStorage | None = None,
        max_upload_bytes: int | None = None,
    ):
        self.provider = provider or YoloFoodRecognitionProvider()
        # ORM 尚未接线时不以进程内数据伪装成可刷新的持久化结果。
        self.repository = repository
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
        started_at = time.perf_counter()
        content, extension, mime_type = await self._read_and_validate_image(image)
        temp_path = self._create_temp_file(content, extension)
        recognition_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        object_name = self._build_object_name(user_id, now, recognition_id, extension)
        uploaded = False

        try:
            await self._upload_original(object_name, temp_path)
            uploaded = True
            candidates = await self._recognize(temp_path, conf_threshold)
            recognition = FoodRecognitionResponse(
                recognition_id=recognition_id,
                status="recognized",
                image_object_name=object_name,
                model_version=self._model_version(),
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
            try:
                stored = await self._create_record(record)
            except FoodRecognitionPersistenceError:
                await self._compensate_uploaded_object(
                    object_name=object_name,
                    recognition_id=recognition_id,
                    user_id=user_id,
                    started_at=started_at,
                )
                self._log_event(
                    level="warning",
                    recognition_id=recognition_id,
                    user_id=user_id,
                    status="failed",
                    phase="database",
                    started_at=started_at,
                    error_type="persistence",
                )
                raise
            self._log_event(
                level="info",
                recognition_id=recognition_id,
                user_id=user_id,
                status=stored.recognition.status,
                phase="completed",
                started_at=started_at,
            )
            return stored.recognition
        except (FoodRecognitionStorageError, FoodRecognitionProviderError) as exc:
            phase = "minio" if isinstance(exc, FoodRecognitionStorageError) else "provider"
            try:
                await self._persist_failure(
                    user_id=user_id,
                    recognition_id=recognition_id,
                    object_name=object_name,
                    mime_type=mime_type,
                    image_size=len(content),
                    conf_threshold=conf_threshold,
                    occurred_at=now,
                    error=exc,
                )
            except FoodRecognitionPersistenceError:
                if uploaded:
                    await self._compensate_uploaded_object(
                        object_name=object_name,
                        recognition_id=recognition_id,
                        user_id=user_id,
                        started_at=started_at,
                    )
                self._log_event(
                    level="warning",
                    recognition_id=recognition_id,
                    user_id=user_id,
                    status="failed",
                    phase="database",
                    started_at=started_at,
                    error_type="persistence",
                )
                raise
            self._log_event(
                level="warning",
                recognition_id=recognition_id,
                user_id=user_id,
                status="failed",
                phase=phase,
                started_at=started_at,
                error_type=type(exc).__name__,
            )
            raise
        finally:
            self._remove_temp_file(temp_path)

    async def get_recognition(
        self, *, user_id: int, recognition_id: str
    ) -> FoodRecognitionResponse:
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
        if record.recognition.status == "failed":
            raise FoodRecognitionStateError("失败的食物识别任务不能确认食材")

        started_at = time.perf_counter()
        now = datetime.now(timezone.utc)
        updated_recognition = record.recognition.model_copy(
            update={
                "status": "confirmed",
                "confirmed_ingredients": confirmed_ingredients,
                "confirmed_at": now,
                "updated_at": now,
            },
            deep=True,
        )
        updated = await self._update_record(
            FoodRecognitionRecord(
                user_id=record.user_id,
                recognition=updated_recognition,
                image_mime_type=record.image_mime_type,
                image_size=record.image_size,
                error_message=record.error_message,
            )
        )
        if updated is None:
            raise FoodRecognitionNotFoundError(recognition_id)
        self._log_event(
            level="info",
            recognition_id=recognition_id,
            user_id=user_id,
            status=updated.recognition.status,
            phase="confirmation",
            started_at=started_at,
        )
        return updated.recognition

    def _validate_conf_threshold(self, conf_threshold: float) -> None:
        if not isinstance(conf_threshold, (int, float)) or not 0 <= conf_threshold <= 1:
            raise FoodRecognitionValidationError("置信度阈值必须位于 0 到 1 之间")

    async def _read_and_validate_image(self, image: UploadFile) -> tuple[bytes, str, str]:
        filename = image.filename or ""
        extension = Path(filename).suffix.lower()
        allowed_mime_types = self._MIME_TYPES_BY_EXTENSION.get(extension)
        if not allowed_mime_types:
            raise FoodRecognitionValidationError("仅支持上传一张 JPG 或 PNG 图片")

        declared_mime_type = (image.content_type or "").split(";", maxsplit=1)[0].lower()
        if declared_mime_type not in allowed_mime_types:
            raise FoodRecognitionValidationError("文件扩展名与 MIME 类型不匹配")

        content = await image.read(self.max_upload_bytes + 1)
        if not content:
            raise FoodRecognitionValidationError("上传图片不能为空")
        if len(content) > self.max_upload_bytes:
            raise FoodRecognitionValidationError(
                f"图片大小不能超过 {self.max_upload_bytes // (1024 * 1024)} MB"
            )
        if not content.startswith(self._IMAGE_HEADERS_BY_EXTENSION[extension]):
            raise FoodRecognitionValidationError("上传文件不是与扩展名匹配的有效图片")

        mime_type = "image/png" if extension == ".png" else "image/jpeg"
        return content, extension, mime_type

    @staticmethod
    def _create_temp_file(content: bytes, extension: str) -> str:
        temp_path = Path(tempfile.gettempdir()) / f"food-recognition-{uuid.uuid4()}{extension}"
        with temp_path.open("xb") as temp_file:
            temp_file.write(content)
        return str(temp_path)

    @staticmethod
    def _build_object_name(
        user_id: int,
        occurred_at: datetime,
        recognition_id: str,
        extension: str,
    ) -> str:
        return (
            f"food-recognitions/{user_id}/{occurred_at:%Y}/{occurred_at:%m}/"
            f"{occurred_at:%d}/{recognition_id}{extension}"
        )

    async def _upload_original(self, object_name: str, temp_path: str) -> None:
        storage = self._get_object_storage()
        try:
            await asyncio.to_thread(storage.upload_file, object_name, temp_path)
        except FoodRecognitionStorageError:
            raise
        except Exception as exc:
            raise FoodRecognitionStorageError(detail=type(exc).__name__) from exc

    async def _delete_uploaded_object(self, object_name: str) -> None:
        """当数据库写入失败时补偿删除已经上传的原图。"""
        storage = self._get_object_storage()
        try:
            await asyncio.to_thread(storage.delete_file, object_name)
        except Exception as exc:
            raise FoodRecognitionStorageError(
                "食物图片补偿删除失败", detail=type(exc).__name__
            ) from exc

    async def _compensate_uploaded_object(
        self,
        *,
        object_name: str,
        recognition_id: str,
        user_id: int,
        started_at: float,
    ) -> None:
        """尽力删除孤立对象，并保留原始数据库异常作为接口结果。"""
        try:
            await self._delete_uploaded_object(object_name)
        except FoodRecognitionStorageError as exc:
            self._log_event(
                level="warning",
                recognition_id=recognition_id,
                user_id=user_id,
                status="failed",
                phase="minio_compensation",
                started_at=started_at,
                error_type=type(exc).__name__,
            )

    def _log_event(
        self,
        *,
        level: str,
        recognition_id: str,
        user_id: int,
        status: str,
        phase: str,
        started_at: float,
        error_type: str | None = None,
    ) -> None:
        """记录可检索的 Food 关键路径日志，不写入文件名、路径或敏感凭据。"""
        elapsed_ms = round((time.perf_counter() - started_at) * 1000)
        message = (
            "food_recognition recognition_id=%s user_id=%s provider=yolo "
            "model_version=%s status=%s phase=%s duration_ms=%s error_type=%s"
        )
        log_method = logger.info if level == "info" else logger.warning
        log_method(
            message,
            recognition_id,
            user_id,
            self._model_version(),
            status,
            phase,
            elapsed_ms,
            error_type or "none",
        )

    def _get_object_storage(self) -> FoodObjectStorage:
        if self._object_storage is None:
            try:
                from app.storage.minio_client import MinIOClient

                self._object_storage = MinIOClient()
            except Exception as exc:
                raise FoodRecognitionStorageError(detail=type(exc).__name__) from exc
        return self._object_storage

    async def _recognize(self, temp_path: str, conf_threshold: float) -> list[IngredientCandidate]:
        try:
            raw_candidates = await self.provider.recognize(temp_path, conf_threshold)
        except FoodRecognitionProviderError:
            raise
        except Exception as exc:
            raise FoodRecognitionInferenceError(detail=type(exc).__name__) from exc

        if not isinstance(raw_candidates, list):
            raise FoodRecognitionInvalidResultError("YOLO 返回了非列表格式的识别结果")

        try:
            candidates = [self._normalize_candidate(candidate) for candidate in raw_candidates]
        except (TypeError, ValidationError) as exc:
            raise FoodRecognitionInvalidResultError(
                "YOLO 返回的识别结果不符合契约", "provider_result_invalid"
            ) from exc

        return self._normalize_candidates(candidates, conf_threshold)

    @staticmethod
    def _normalize_candidate(
        candidate: IngredientCandidate | Mapping[str, Any],
    ) -> IngredientCandidate:
        """归一化类别键，并优先使用项目定义的中文展示名。"""
        if isinstance(candidate, IngredientCandidate):
            payload = candidate.model_dump()
        elif isinstance(candidate, Mapping):
            payload = dict(candidate)
        else:
            raise TypeError("候选项必须是对象")

        key = payload.get("key")
        if isinstance(key, str):
            normalized_key = key.strip().lower().replace(" ", "_")
            payload["key"] = normalized_key
            if name := FOOD_LABEL_NAMES.get(normalized_key):
                payload["name"] = name
        return IngredientCandidate.model_validate(payload)

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
        record = await self._get_record(recognition_id)
        if record is None:
            raise FoodRecognitionNotFoundError(recognition_id)
        if record.user_id != user_id:
            raise FoodRecognitionAccessDeniedError(recognition_id)
        return record

    def _get_repository(self) -> FoodRecognitionRepository:
        if self.repository is None:
            raise FoodRecognitionPersistenceError(
                "食物识别任务持久化仓库尚未接入",
                detail="food_recognition_repository_unavailable",
            )
        return self.repository

    async def _create_record(self, record: FoodRecognitionRecord) -> FoodRecognitionRecord:
        try:
            stored = await self._get_repository().create(record)
        except FoodRecognitionPersistenceError:
            raise
        except Exception as exc:
            raise FoodRecognitionPersistenceError(detail=type(exc).__name__) from exc
        if not isinstance(stored, FoodRecognitionRecord):
            raise FoodRecognitionPersistenceError(detail="invalid_repository_create_result")
        return stored

    async def _get_record(self, recognition_id: str) -> FoodRecognitionRecord | None:
        try:
            record = await self._get_repository().get(recognition_id)
        except FoodRecognitionPersistenceError:
            raise
        except Exception as exc:
            raise FoodRecognitionPersistenceError(detail=type(exc).__name__) from exc
        if record is not None and not isinstance(record, FoodRecognitionRecord):
            raise FoodRecognitionPersistenceError(detail="invalid_repository_get_result")
        return record

    async def _update_record(self, record: FoodRecognitionRecord) -> FoodRecognitionRecord | None:
        try:
            updated = await self._get_repository().update(record)
        except FoodRecognitionPersistenceError:
            raise
        except Exception as exc:
            raise FoodRecognitionPersistenceError(detail=type(exc).__name__) from exc
        if updated is not None and not isinstance(updated, FoodRecognitionRecord):
            raise FoodRecognitionPersistenceError(detail="invalid_repository_update_result")
        return updated

    async def _persist_failure(
        self,
        *,
        user_id: int,
        recognition_id: str,
        object_name: str,
        mime_type: str,
        image_size: int,
        conf_threshold: float,
        occurred_at: datetime,
        error: AppException,
    ) -> None:
        """将上传或推理失败写为 failed，避免形成伪成功任务。"""
        failure = FoodRecognitionResponse(
            recognition_id=recognition_id,
            status="failed",
            image_object_name=object_name,
            model_version=self._model_version(),
            conf_threshold=conf_threshold,
            raw_detections=[],
            created_at=occurred_at,
            updated_at=datetime.now(timezone.utc),
        )
        await self._create_record(
            FoodRecognitionRecord(
                user_id=user_id,
                recognition=failure,
                image_mime_type=mime_type,
                image_size=image_size,
                error_message=error.message[:500],
            )
        )

    def _model_version(self) -> str:
        model_version = str(getattr(self.provider, "model_version", "") or "yolo-unknown")
        return model_version[:100]

    @staticmethod
    def _remove_temp_file(temp_path: str) -> None:
        try:
            Path(temp_path).unlink(missing_ok=True)
        except OSError:
            # 临时文件无法清理不应掩盖原始业务异常；交给系统临时目录策略后续处理。
            pass


food_recognition_service = FoodRecognitionService()
