"""Validate, register, activate, roll back, and remove Food model packages."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import stat
import tempfile
import uuid
import zipfile
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import Any, Callable

import yaml
from PIL import Image
from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.config.settings import Settings
from app.core.exceptions import AppException
from app.entity.db_models import FoodModelVersion, OperationLog, User
from app.entity.food_model_schemas import (
    FoodModelClass,
    FoodModelListResponse,
    FoodModelPackageManifest,
    FoodModelVersionResponse,
)
from app.modeling.food_yolo_runtime import YoloFoodRecognitionProvider, _default_model_loader
from app.repositories.food_model_repository import FoodModelRepository
from app.services.food_recognition_service import set_runtime_food_provider

ModelLoader = Callable[[str], Any]


class FoodModelServiceError(AppException):
    def __init__(self, status_code: int, code: str, message: str) -> None:
        super().__init__(status_code, message, detail=code)
        self.error_code = code


class InvalidFoodModelPackageError(FoodModelServiceError):
    def __init__(self, message: str = "模型包校验失败") -> None:
        super().__init__(422, "INVALID_MODEL_PACKAGE", message)


class FoodModelNotFoundError(FoodModelServiceError):
    def __init__(self) -> None:
        super().__init__(404, "FOOD_MODEL_NOT_FOUND", "Food 模型不存在")


class FoodModelConflictError(FoodModelServiceError):
    def __init__(self, message: str) -> None:
        super().__init__(409, "FOOD_MODEL_CONFLICT", message)


class FoodModelService:
    MAX_UNCOMPRESSED_BYTES = 1024 * 1024 * 1024
    MAX_ARCHIVE_MEMBERS = 32
    MAX_COMPRESSION_RATIO = 100
    REQUIRED_FILES = {"best.pt", "classes.yaml", "manifest.json"}

    def __init__(
        self,
        db: Session,
        *,
        settings: Settings | None = None,
        model_loader: ModelLoader | None = None,
    ) -> None:
        self.db = db
        self.repository = FoodModelRepository(db)
        self.settings = settings or Settings()
        self.registry_root = Path(self.settings.FOOD_MODEL_REGISTRY_DIR).resolve()
        self.model_loader = model_loader or _default_model_loader

    def list_versions(self) -> FoodModelListResponse:
        records = self.repository.list_versions()
        active = next((record.id for record in records if record.is_active), None)
        return FoodModelListResponse(
            active_model_id=active,
            items=[self._to_response(record) for record in records],
        )

    def register_package(self, package_path: Path, actor: User) -> FoodModelVersionResponse:
        if package_path.stat().st_size > self.settings.FOOD_MODEL_MAX_PACKAGE_BYTES:
            raise InvalidFoodModelPackageError("模型包不得超过 512 MiB")
        self.registry_root.mkdir(parents=True, exist_ok=True)
        temp_dir = self.registry_root / f".upload-{uuid.uuid4().hex}"
        temp_dir.mkdir()
        record: FoodModelVersion | None = None
        try:
            self._extract_package(package_path, temp_dir)
            manifest = self._load_manifest(temp_dir / "manifest.json")
            if self.repository.get_by_version(manifest.version) is not None:
                raise FoodModelConflictError("该模型版本已存在")
            target_dir = (self.registry_root / manifest.version).resolve()
            if target_dir.parent != self.registry_root or target_dir.exists():
                raise FoodModelConflictError("模型版本目录已存在")

            weights_path = temp_dir / manifest.weights_file
            classes_path = temp_dir / manifest.classes_file
            weight_hash = self._sha256(weights_path)
            classes_hash = self._sha256(classes_path)
            if weight_hash != manifest.weights_sha256:
                raise InvalidFoodModelPackageError("best.pt Hash 与 manifest 不一致")
            if classes_hash != manifest.classes_sha256:
                raise InvalidFoodModelPackageError("classes.yaml Hash 与 manifest 不一致")
            classes = self._load_classes(classes_path)
            if len(classes) != manifest.class_count:
                raise InvalidFoodModelPackageError("类别数量与 manifest 不一致")

            os.replace(temp_dir, target_dir)
            temp_dir = target_dir
            record = self.repository.create(
                name=manifest.name,
                version=manifest.version,
                task=manifest.task,
                status="validating",
                weights_path=str(target_dir / manifest.weights_file),
                classes_path=str(target_dir / manifest.classes_file),
                weight_sha256=weight_hash,
                classes_sha256=classes_hash,
                file_size=(target_dir / manifest.weights_file).stat().st_size,
                class_count=len(classes),
                classes=classes,
                manifest=manifest.model_dump(mode="json"),
                is_active=False,
                uploaded_by=actor.id,
            )
            try:
                self._validate_model(record)
            except Exception as exc:
                self.repository.mark_failed(record, "模型任务、类别或推理输出校验失败")
                self._audit(actor, "validate_failed", record, "模型包运行校验失败", "failure")
                raise InvalidFoodModelPackageError("模型任务、类别或推理输出校验失败") from exc

            record = self.repository.mark_ready(record, datetime.now().astimezone())
            self._audit(actor, "upload", record, "上传并校验 Food 模型包")
            return self._to_response(record)
        except (FoodModelServiceError, zipfile.BadZipFile, OSError, KeyError, TypeError, ValueError, yaml.YAMLError, ValidationError) as exc:
            if isinstance(exc, FoodModelServiceError):
                raise
            raise InvalidFoodModelPackageError() from exc
        finally:
            if record is None and temp_dir.exists():
                shutil.rmtree(temp_dir, ignore_errors=True)

    def activate(self, model_id: int, actor: User) -> FoodModelVersionResponse:
        record = self.repository.get(model_id)
        if record is None:
            raise FoodModelNotFoundError()
        if record.status not in {"ready", "active"}:
            raise FoodModelConflictError("仅校验通过的模型可以启用")
        try:
            provider, display_names = self._build_provider(record, smoke_test=True)
        except Exception as exc:
            if not record.is_active:
                self.repository.mark_failed(record, "启用前推理校验失败")
            self._audit(actor, "activate_failed", record, "模型热切换失败", "failure")
            raise InvalidFoodModelPackageError("启用前推理校验失败，已保留原模型") from exc

        record = self.repository.activate(
            record,
            actor_id=actor.id,
            activated_at=datetime.now().astimezone(),
        )
        set_runtime_food_provider(provider, "yolo", record.version, display_names)
        self._audit(actor, "activate", record, "热切换 Food 推理模型")
        return self._to_response(record)

    def rollback(self, actor: User) -> FoodModelVersionResponse:
        active = self.repository.get_active()
        if active is None:
            raise FoodModelConflictError("当前没有可回滚的活跃模型")
        candidate = self.repository.get_rollback_candidate(active.id)
        if candidate is None:
            raise FoodModelConflictError("没有可回滚的历史健康模型")
        return self.activate(candidate.id, actor)

    def delete(self, model_id: int, actor: User) -> None:
        record = self.repository.get(model_id)
        if record is None:
            raise FoodModelNotFoundError()
        if record.is_active:
            raise FoodModelConflictError("活跃模型不能删除")
        if record.status == "ready" and self.repository.healthy_count() <= 1:
            raise FoodModelConflictError("最后一个健康模型不能删除")
        model_dir = Path(record.weights_path).resolve().parent
        if model_dir.parent != self.registry_root:
            raise FoodModelConflictError("模型目录不在受控存储中")
        quarantine = self.registry_root / f".delete-{uuid.uuid4().hex}"
        os.replace(model_dir, quarantine)
        try:
            self.db.delete(record)
            self.db.add(
                OperationLog(
                    user_id=actor.id,
                    username=actor.username,
                    module="model",
                    action="delete",
                    target_type="food_model",
                    target_id=str(model_id),
                    description="删除非活跃 Food 模型",
                    status="success",
                )
            )
            self.db.commit()
        except Exception:
            self.db.rollback()
            os.replace(quarantine, model_dir)
            raise
        shutil.rmtree(quarantine, ignore_errors=False)

    def initialize_active_runtime(self) -> bool:
        try:
            active = self.repository.get_active()
        except SQLAlchemyError:
            self.db.rollback()
            return False
        if active is None:
            return False
        try:
            provider, display_names = self._build_provider(active, smoke_test=False)
        except Exception:
            return False
        set_runtime_food_provider(provider, "yolo", active.version, display_names)
        return True

    def _extract_package(self, package_path: Path, destination: Path) -> None:
        with zipfile.ZipFile(package_path) as archive:
            members = archive.infolist()
            if len(members) > self.MAX_ARCHIVE_MEMBERS:
                raise InvalidFoodModelPackageError("模型包文件数量过多")
            names = [member.filename.replace("\\", "/") for member in members if not member.is_dir()]
            if len(names) != len(set(names)):
                raise InvalidFoodModelPackageError("模型包包含重复文件")
            if not self.REQUIRED_FILES.issubset(names):
                raise InvalidFoodModelPackageError("模型包缺少 best.pt、classes.yaml 或 manifest.json")
            if sum(member.file_size for member in members) > self.MAX_UNCOMPRESSED_BYTES:
                raise InvalidFoodModelPackageError("模型包解压后体积过大")
            for member in members:
                name = member.filename.replace("\\", "/")
                path = PurePosixPath(name)
                mode = member.external_attr >> 16
                if path.is_absolute() or ".." in path.parts or stat.S_ISLNK(mode):
                    raise InvalidFoodModelPackageError("模型包包含不安全路径")
                if member.is_dir():
                    continue
                if member.file_size and member.compress_size == 0:
                    raise InvalidFoodModelPackageError("模型包压缩比例异常")
                if member.compress_size and member.file_size / member.compress_size > self.MAX_COMPRESSION_RATIO:
                    raise InvalidFoodModelPackageError("模型包压缩比例异常")
                if name not in self.REQUIRED_FILES and not (
                    name.startswith("samples/") and Path(name).suffix.lower() in {".jpg", ".jpeg", ".png"}
                ):
                    raise InvalidFoodModelPackageError("模型包包含未允许的文件")
                target = destination.joinpath(*path.parts)
                target.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(member) as source, target.open("xb") as output:
                    shutil.copyfileobj(source, output, length=1024 * 1024)

    @staticmethod
    def _load_manifest(path: Path) -> FoodModelPackageManifest:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return FoodModelPackageManifest.model_validate(payload)

    @staticmethod
    def _load_classes(path: Path) -> list[dict[str, Any]]:
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        names = payload.get("names")
        if not isinstance(names, dict):
            raise InvalidFoodModelPackageError("classes.yaml 的 names 必须是映射")
        classes: list[dict[str, Any]] = []
        for raw_id, definition in names.items():
            if not isinstance(definition, dict):
                raise InvalidFoodModelPackageError("每个类别必须包含中英文名称")
            classes.append(
                {
                    "class_id": int(raw_id),
                    "class_name": str(definition["class_name"]).strip(),
                    "display_name": str(definition["display_name"]).strip(),
                }
            )
        classes.sort(key=lambda item: item["class_id"])
        if [item["class_id"] for item in classes] != list(range(len(classes))):
            raise InvalidFoodModelPackageError("类别 ID 必须从 0 连续排列")
        if any(not item["class_name"] or not item["display_name"] for item in classes):
            raise InvalidFoodModelPackageError("类别名称不能为空")
        class_names = [item["class_name"] for item in classes]
        if len(class_names) != len(set(class_names)):
            raise InvalidFoodModelPackageError("英文类别标识不得重复")
        return classes

    def _validate_model(self, record: FoodModelVersion) -> None:
        model = self.model_loader(record.weights_path)
        model_task = str(getattr(model, "task", ""))
        if model_task and model_task != record.task:
            raise ValueError("model task mismatch")
        raw_names = getattr(model, "names", None)
        expected_names = [item["class_name"] for item in record.classes]
        if isinstance(raw_names, dict):
            model_names = [str(raw_names[index]) for index in sorted(raw_names)]
        elif isinstance(raw_names, (list, tuple)):
            model_names = [str(name) for name in raw_names]
        else:
            raise ValueError("model names unavailable")
        if model_names != expected_names:
            raise ValueError("model class names mismatch")
        self._smoke_predict(model)

    def _build_provider(
        self, record: FoodModelVersion, *, smoke_test: bool
    ) -> tuple[YoloFoodRecognitionProvider, dict[str, str]]:
        provider = YoloFoodRecognitionProvider(
            record.weights_path,
            record.classes_path,
            task=record.task,
            model_loader=self.model_loader,
        )
        if not provider.is_available():
            raise ValueError("model unavailable")
        if smoke_test:
            with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as handle:
                smoke_path = Path(handle.name)
            try:
                Image.new("RGB", (64, 64), color=(240, 240, 240)).save(smoke_path, "JPEG")
                provider.recognize(str(smoke_path.resolve()), 0.0)
            finally:
                smoke_path.unlink(missing_ok=True)
        display_names = {
            item["class_name"]: item["display_name"] for item in record.classes
        }
        return provider, display_names

    @staticmethod
    def _smoke_predict(model: Any) -> None:
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as handle:
            smoke_path = Path(handle.name)
        try:
            Image.new("RGB", (64, 64), color=(240, 240, 240)).save(smoke_path, "JPEG")
            results = model.predict(source=str(smoke_path), imgsz=64, verbose=False)
            if results is None:
                raise ValueError("empty prediction response")
        finally:
            smoke_path.unlink(missing_ok=True)

    @staticmethod
    def _sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as file:
            for chunk in iter(lambda: file.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def _audit(
        self,
        actor: User,
        action: str,
        record: FoodModelVersion,
        description: str,
        status_value: str = "success",
    ) -> None:
        self.db.add(
            OperationLog(
                user_id=actor.id,
                username=actor.username,
                module="model",
                action=action,
                target_type="food_model",
                target_id=str(record.id),
                description=description,
                status=status_value,
            )
        )
        self.db.commit()

    @staticmethod
    def _to_response(record: FoodModelVersion) -> FoodModelVersionResponse:
        manifest = record.manifest or {}
        return FoodModelVersionResponse(
            model_id=record.id,
            name=record.name,
            version=record.version,
            task=record.task,
            status=record.status,
            is_active=record.is_active,
            available=record.status in {"ready", "active"},
            class_count=record.class_count,
            classes=[FoodModelClass.model_validate(item) for item in (record.classes or [])],
            weight_sha256=record.weight_sha256,
            classes_sha256=record.classes_sha256,
            file_size=record.file_size,
            dataset=manifest.get("dataset"),
            metrics=manifest.get("metrics"),
            validation_error=record.validation_error,
            created_at=record.created_at,
            validated_at=record.validated_at,
            activated_at=record.activated_at,
        )
