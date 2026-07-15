"""黄小石模型接口的 V1 适配层，以及可关闭的本地 Mock Provider。"""

from __future__ import annotations

from pathlib import Path
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


DEFAULT_DISPLAY_NAMES = {
    "apple": "苹果",
    "beef": "牛肉",
    "carrot": "胡萝卜",
    "chicken": "鸡肉",
    "cucumber": "黄瓜",
    "egg": "鸡蛋",
    "onion": "洋葱",
    "pork": "猪肉",
    "potato": "土豆",
    "rice": "大米",
    "tomato": "番茄",
}


class MockFoodRecognitionProvider:
    """Day 3 可运行的固定 Mock Provider，默认仅用于开发和测试。"""

    provider_name = "mock"
    model_version = "food-mock-v1"

    def recognize(
        self,
        image_path: str,
        conf_threshold: float = 0.25,
    ) -> list[ModelDetection]:
        del image_path
        detections = [
            ModelDetection(
                class_name="tomato",
                confidence=0.9321,
                bbox=BoundingBox(x1=120.4, y1=80.2, x2=310.7, y2=265.1),
            ),
            ModelDetection(
                class_name="egg",
                confidence=0.8812,
                bbox=BoundingBox(x1=350.0, y1=100.0, x2=470.0, y2=230.0),
            ),
        ]
        return [item for item in detections if item.confidence >= conf_threshold]

    def get_display_name(self, class_name: str) -> str:
        return DEFAULT_DISPLAY_NAMES.get(class_name, class_name)


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
        return DEFAULT_DISPLAY_NAMES.get(class_name, class_name)


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
        return DEFAULT_DISPLAY_NAMES.get(class_name, class_name)


def build_food_recognition_provider() -> FoodRecognitionProvider:
    """根据 V1 环境变量构建唯一的 Provider，不在真实模式自动降级。"""
    if settings.FOOD_PROVIDER == "mock":
        return MockFoodRecognitionProvider()
    if settings.FOOD_PROVIDER == "yolo":
        try:
            return YoloFoodRecognitionProvider()
        except FoodModelUnavailableError as exc:
            return UnavailableFoodRecognitionProvider(exc)
    raise FoodModelUnavailableError("未配置有效的食物识别 Provider")
