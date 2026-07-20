from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database.session import Base
from app.entity.db_models import FoodModelVersion, OperationLog, User
from app.services.food_model_service import (
    FoodModelConflictError,
    FoodModelService,
    InvalidFoodModelPackageError,
)
from app.services.food_recognition_service import clear_runtime_food_provider


class FakeModel:
    task = "detect"
    names = {0: "tomato", 1: "egg"}

    def __init__(self, *, fail_predict: bool = False) -> None:
        self.fail_predict = fail_predict

    def predict(self, **_):
        if self.fail_predict:
            raise RuntimeError("test-only inference failure")
        return [SimpleNamespace(boxes=[])]


class FakeClassifyModel:
    task = "classify"
    names = {0: "tomato", 1: "egg"}

    def predict(self, **_):
        return [SimpleNamespace(probs=SimpleNamespace(top1=0, top1conf=0.91))]


@pytest.fixture(autouse=True)
def isolate_runtime_provider():
    clear_runtime_food_provider()
    yield
    clear_runtime_food_provider()


@pytest.fixture
def model_context(tmp_path: Path):
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    actor = User(username="model_admin", email="model@example.com", hashed_password="x")
    db.add(actor)
    db.commit()
    db.refresh(actor)
    settings = SimpleNamespace(
        FOOD_MODEL_REGISTRY_DIR=str(tmp_path / "registry"),
        FOOD_MODEL_MAX_PACKAGE_BYTES=32 * 1024 * 1024,
    )
    try:
        yield db, actor, settings
    finally:
        db.close()
        engine.dispose()


def sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def make_package(
    tmp_path: Path,
    version: str,
    *,
    weights_hash: str | None = None,
    extra_files: dict[str, bytes] | None = None,
    task: str = "detect",
    compression: int = zipfile.ZIP_STORED,
) -> Path:
    weights = f"test-model-{version}".encode()
    classes = (
        "names:\n"
        "  0:\n"
        "    class_name: tomato\n"
        "    display_name: 番茄\n"
        "  1:\n"
        "    class_name: egg\n"
        "    display_name: 鸡蛋\n"
    ).encode()
    manifest = {
        "schema_version": 1,
        "name": "Food Detect",
        "version": version,
        "task": task,
        "weights_file": "best.pt",
        "classes_file": "classes.yaml",
        "weights_sha256": weights_hash or sha256(weights),
        "classes_sha256": sha256(classes),
        "class_count": 2,
        "trained_at": "2026-07-20T00:00:00+08:00",
    }
    package = tmp_path / f"{version}.zip"
    with zipfile.ZipFile(package, "w", compression=compression) as archive:
        archive.writestr("best.pt", weights)
        archive.writestr("classes.yaml", classes)
        archive.writestr("manifest.json", json.dumps(manifest))
        for name, content in (extra_files or {}).items():
            archive.writestr(name, content)
    return package


def test_register_activate_rollback_and_delete_are_persistent(model_context, tmp_path):
    db, actor, settings = model_context
    service = FoodModelService(db, settings=settings, model_loader=lambda _: FakeModel())

    first = service.register_package(make_package(tmp_path, "food-v1"), actor)
    assert first.status == "ready"
    assert not hasattr(first, "weights_path")
    service.activate(first.model_id, actor)

    second = service.register_package(make_package(tmp_path, "food-v2"), actor)
    active_second = service.activate(second.model_id, actor)
    assert active_second.is_active is True
    assert service.rollback(actor).model_id == first.model_id

    with pytest.raises(FoodModelConflictError, match="活跃模型"):
        service.delete(first.model_id, actor)

    service.delete(second.model_id, actor)
    assert db.get(FoodModelVersion, second.model_id) is None
    assert not (Path(settings.FOOD_MODEL_REGISTRY_DIR) / "food-v2").exists()
    assert db.query(OperationLog).filter(OperationLog.module == "model").count() >= 5


def test_invalid_hash_and_path_traversal_never_register_a_model(model_context, tmp_path):
    db, actor, settings = model_context
    service = FoodModelService(db, settings=settings, model_loader=lambda _: FakeModel())

    with pytest.raises(InvalidFoodModelPackageError, match="Hash"):
        service.register_package(
            make_package(tmp_path, "bad-hash", weights_hash="0" * 64), actor
        )

    with pytest.raises(InvalidFoodModelPackageError, match="不安全路径"):
        service.register_package(
            make_package(tmp_path, "bad-path", extra_files={"../escape.txt": b"x"}),
            actor,
        )

    assert db.query(FoodModelVersion).count() == 0
    assert not (tmp_path / "escape.txt").exists()


def test_failed_hot_switch_keeps_the_previous_model_active(model_context, tmp_path):
    db, actor, settings = model_context
    loads: dict[str, int] = {}

    def loader(path: str):
        version = Path(path).parent.name
        loads[version] = loads.get(version, 0) + 1
        return FakeModel(fail_predict=version == "candidate" and loads[version] > 1)

    service = FoodModelService(db, settings=settings, model_loader=loader)
    stable = service.register_package(make_package(tmp_path, "stable"), actor)
    service.activate(stable.model_id, actor)
    candidate = service.register_package(make_package(tmp_path, "candidate"), actor)

    with pytest.raises(InvalidFoodModelPackageError, match="已保留原模型"):
        service.activate(candidate.model_id, actor)

    db.expire_all()
    assert db.get(FoodModelVersion, stable.model_id).is_active is True
    assert db.get(FoodModelVersion, candidate.model_id).status == "failed"


def test_classification_package_can_be_validated_and_activated(model_context, tmp_path):
    db, actor, settings = model_context
    service = FoodModelService(
        db,
        settings=settings,
        model_loader=lambda _: FakeClassifyModel(),
    )

    registered = service.register_package(
        make_package(tmp_path, "food-cls-v1", task="classify"), actor
    )
    activated = service.activate(registered.model_id, actor)

    assert activated.task == "classify"
    assert activated.is_active is True


def test_task_and_embedded_class_mismatches_are_rejected(model_context, tmp_path):
    db, actor, settings = model_context
    task_service = FoodModelService(
        db,
        settings=settings,
        model_loader=lambda _: FakeClassifyModel(),
    )
    with pytest.raises(InvalidFoodModelPackageError, match="任务、类别"):
        task_service.register_package(make_package(tmp_path, "task-mismatch"), actor)

    wrong_names_model = FakeModel()
    wrong_names_model.names = {0: "egg", 1: "tomato"}
    class_service = FoodModelService(
        db,
        settings=settings,
        model_loader=lambda _: wrong_names_model,
    )
    with pytest.raises(InvalidFoodModelPackageError, match="任务、类别"):
        class_service.register_package(make_package(tmp_path, "class-mismatch"), actor)

    assert {
        record.status for record in db.query(FoodModelVersion).all()
    } == {"failed"}


def test_zip_bomb_ratio_and_last_healthy_delete_are_rejected(model_context, tmp_path):
    db, actor, settings = model_context
    service = FoodModelService(db, settings=settings, model_loader=lambda _: FakeModel())

    with pytest.raises(InvalidFoodModelPackageError, match="压缩比例"):
        service.register_package(
            make_package(
                tmp_path,
                "compressed-bomb",
                compression=zipfile.ZIP_DEFLATED,
                extra_files={"samples/example.jpg": b"0" * 200_000},
            ),
            actor,
        )

    only_healthy = service.register_package(make_package(tmp_path, "only-healthy"), actor)
    with pytest.raises(FoodModelConflictError, match="最后一个健康模型"):
        service.delete(only_healthy.model_id, actor)
