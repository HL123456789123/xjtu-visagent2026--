"""食品识别 YOLO 模型的 V1 适配层。"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from threading import Lock
from typing import Protocol, runtime_checkable

from app.config.settings import settings
from app.entity.food_schemas import BoundingBox, ModelDetection


class FoodModelUnavailableError(Exception):
    """模型权重、类别文件或推理运行时不可用。"""


@runtime_checkable
class FoodRecognitionProvider(Protocol):
    """V1 冻结的模型接口：同步输入本地绝对路径，输出 ModelDetection。"""

    provider_name: str
    model_version: str

    def recognize(
        self,
        image_path: str,
        conf_threshold: float = 0.25,
    ) -> list[ModelDetection]:
        """识别一张图片；无目标返回空列表。"""

    def get_display_name(self, class_name: str) -> str:
        """将冻结的英文类别名映射为展示名称。"""


class UnavailableFoodRecognitionProvider:
    """延迟报告初始化失败，确保 API 仍能按 V1 返回 HTTP 503。"""

    provider_name = "yolo"

    def __init__(self, error: FoodModelUnavailableError, model_version: str | None = None):
        self.error = error
        self.model_version = model_version or settings.FOOD_MODEL_VERSION

    def recognize(
        self,
        image_path: str,
        conf_threshold: float = 0.25,
    ) -> list[ModelDetection]:
        del image_path, conf_threshold
        raise self.error

    def get_display_name(self, class_name: str) -> str:
        return class_name


class YoloFoodRecognitionProvider:
    """读取 ``best.pt`` 与 ``classes.yaml`` 的真实 YOLO V1 Provider。"""

    provider_name = "yolo"

    def __init__(
        self,
        model_path: str | None = None,
        classes_path: str | None = None,
        model_version: str | None = None,
    ):
        self.model_path = Path(model_path or settings.FOOD_MODEL_PATH)
        self.classes_path = Path(classes_path or settings.FOOD_CLASSES_PATH)
        self.model_version = model_version or settings.FOOD_MODEL_VERSION
        self._model = None
        self._model_lock = Lock()
        self._class_definitions = self._load_classes()

    def _load_classes(self) -> dict[int, tuple[str, str]]:
        if not self.classes_path.is_file():
            raise FoodModelUnavailableError(f"类别文件不存在: {self.classes_path}")
        try:
            import yaml

            payload = yaml.safe_load(self.classes_path.read_text(encoding="utf-8")) or {}
            names = payload.get("names", {})
            if not isinstance(names, dict):
                raise ValueError("names 必须是映射")
            definitions: dict[int, tuple[str, str]] = {}
            for raw_index, raw_item in names.items():
                index = int(raw_index)
                if not isinstance(raw_item, dict):
                    raise ValueError("类别定义必须包含 class_name 和 display_name")
                class_name = str(raw_item["class_name"]).strip().lower().replace(" ", "_")
                display_name = str(raw_item["display_name"]).strip()
                if not class_name or not display_name:
                    raise ValueError("类别定义不能为空")
                definitions[index] = (class_name, display_name)
            if not definitions:
                raise ValueError("类别文件没有可用类别")
            return definitions
        except FoodModelUnavailableError:
            raise
        except Exception as exc:
            raise FoodModelUnavailableError("类别文件格式无效") from exc

    def _get_model(self):
        if self._model is not None:
            return self._model
        with self._model_lock:
            if self._model is not None:
                return self._model
            if not self.model_path.is_file():
                raise FoodModelUnavailableError(f"模型权重不存在: {self.model_path}")
            try:
                from ultralytics import YOLO

                self._model = YOLO(str(self.model_path))
                return self._model
            except Exception as exc:
                raise FoodModelUnavailableError("食物识别模型加载失败") from exc

    def recognize(
        self,
        image_path: str,
        conf_threshold: float = 0.25,
    ) -> list[ModelDetection]:
        if not 0 <= conf_threshold <= 1:
            raise ValueError("conf_threshold 必须位于 0 到 1 之间")
        if not Path(image_path).is_file():
            raise FoodModelUnavailableError("待识别图片不存在")
        try:
            results = self._get_model().predict(
                source=image_path,
                conf=conf_threshold,
                verbose=False,
            )
            detections: list[ModelDetection] = []
            for result in results:
                boxes = getattr(result, "boxes", None)
                if boxes is None:
                    continue
                for box in boxes:
                    class_index = int(box.cls[0].item())
                    if class_index not in self._class_definitions:
                        continue
                    class_name, _ = self._class_definitions[class_index]
                    x1, y1, x2, y2 = (float(value) for value in box.xyxy[0].tolist())
                    detections.append(
                        ModelDetection(
                            class_name=class_name,
                            confidence=float(box.conf[0].item()),
                            bbox=BoundingBox(x1=x1, y1=y1, x2=x2, y2=y2),
                        )
                    )
            return detections
        except FoodModelUnavailableError:
            raise
        except Exception as exc:
            raise FoodModelUnavailableError("食物识别模型推理失败") from exc

    def get_display_name(self, class_name: str) -> str:
        for configured_name, display_name in self._class_definitions.values():
            if configured_name == class_name:
                return display_name
        return class_name


@lru_cache(maxsize=1)
def _get_yolo_provider(
    model_path: str,
    classes_path: str,
    model_version: str,
) -> YoloFoodRecognitionProvider:
    """在同一进程内复用唯一的真实 YOLO Provider。"""
    return YoloFoodRecognitionProvider(model_path, classes_path, model_version)


def build_food_recognition_provider() -> FoodRecognitionProvider:
    """按当前配置复用真实 YOLO Provider；初始化失败时延迟映射为 API 503。"""
    try:
        return _get_yolo_provider(
            settings.FOOD_MODEL_PATH,
            settings.FOOD_CLASSES_PATH,
            settings.FOOD_MODEL_VERSION,
        )
    except FoodModelUnavailableError as exc:
        return UnavailableFoodRecognitionProvider(exc)
