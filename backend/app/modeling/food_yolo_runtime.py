"""Single-image YOLO provider at the V1.1 model boundary.

The Food service owns batch validation, iteration, ``image_index`` assignment,
storage, and aggregation. This module deliberately knows nothing about HTTP or
the database and never accepts a list of images.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from typing import Any, Callable, Protocol

import yaml


@dataclass(frozen=True, slots=True)
class BoundingBox:
    x1: float
    y1: float
    x2: float
    y2: float


@dataclass(frozen=True, slots=True)
class ModelDetection:
    class_name: str
    confidence: float
    bbox: BoundingBox


class FoodModelUnavailableError(RuntimeError):
    """Raised when the configured YOLO runtime cannot serve inference."""


class FoodRecognitionProvider(Protocol):
    def recognize(
        self,
        image_path: str,
        conf_threshold: float = 0.25,
    ) -> list[ModelDetection]: ...


ModelLoader = Callable[[str], Any]


def _default_model_loader(weights_path: str) -> Any:
    try:
        from ultralytics import YOLO
    except ImportError as exc:  # pragma: no cover - depends on deployment image
        raise FoodModelUnavailableError("ultralytics is not installed") from exc
    return YOLO(weights_path)


def _load_class_names(classes_path: Path) -> dict[int, str]:
    try:
        payload = yaml.safe_load(classes_path.read_text(encoding="utf-8")) or {}
        raw_names = payload["names"]
        if not isinstance(raw_names, dict):
            raise TypeError("names must be a mapping")
        names: dict[int, str] = {}
        for raw_index, definition in raw_names.items():
            if not isinstance(definition, dict) or not definition.get("class_name"):
                raise TypeError("each class must define class_name")
            names[int(raw_index)] = str(definition["class_name"])
        if sorted(names) != list(range(len(names))):
            raise ValueError("class ids must be continuous from zero")
        return names
    except (OSError, KeyError, TypeError, ValueError, yaml.YAMLError) as exc:
        raise FoodModelUnavailableError(f"invalid classes file: {classes_path}") from exc


class YoloFoodRecognitionProvider:
    """Lazily loads one YOLO model and reuses it for single-image inference."""

    def __init__(
        self,
        model_path: str,
        classes_path: str,
        *,
        device: str | int | None = None,
        image_size: int = 640,
        model_loader: ModelLoader | None = None,
    ) -> None:
        self._model_path = Path(model_path)
        self._classes = _load_class_names(Path(classes_path))
        self._device = device
        self._image_size = image_size
        self._model_loader = model_loader or _default_model_loader
        self._model: Any | None = None
        self._model_lock = Lock()

    def _get_model(self) -> Any:
        if self._model is not None:
            return self._model
        with self._model_lock:
            if self._model is not None:
                return self._model
            if not self._model_path.is_file():
                raise FoodModelUnavailableError(
                    f"food model weights not found: {self._model_path}"
                )
            try:
                self._model = self._model_loader(str(self._model_path))
            except FoodModelUnavailableError:
                raise
            except Exception as exc:
                raise FoodModelUnavailableError("failed to load food model") from exc
            return self._model

    def is_available(self) -> bool:
        """Load-check the configured runtime without exposing its path."""
        try:
            self._get_model()
        except FoodModelUnavailableError:
            return False
        return True

    def recognize(
        self,
        image_path: str,
        conf_threshold: float = 0.25,
    ) -> list[ModelDetection]:
        if not 0 <= conf_threshold <= 1:
            raise ValueError("conf_threshold must be between 0 and 1")
        image = Path(image_path)
        if not image.is_absolute() or not image.is_file():
            raise ValueError("image_path must be an existing absolute file path")

        predict_options: dict[str, Any] = {
            "source": str(image),
            "conf": conf_threshold,
            "imgsz": self._image_size,
            "verbose": False,
        }
        if self._device is not None:
            predict_options["device"] = self._device

        try:
            results = self._get_model().predict(**predict_options)
        except FoodModelUnavailableError:
            raise
        except Exception as exc:
            raise FoodModelUnavailableError("food model inference failed") from exc

        if not results:
            return []
        boxes = getattr(results[0], "boxes", None)
        if boxes is None:
            return []

        detections: list[ModelDetection] = []
        for box in boxes:
            try:
                class_id = int(box.cls[0].item())
                confidence = float(box.conf[0].item())
                x1, y1, x2, y2 = (float(value) for value in box.xyxy[0].tolist())
                class_name = self._classes[class_id]
            except (AttributeError, IndexError, KeyError, TypeError, ValueError) as exc:
                raise FoodModelUnavailableError("food model returned an invalid detection") from exc
            detections.append(
                ModelDetection(
                    class_name=class_name,
                    confidence=confidence,
                    bbox=BoundingBox(x1=x1, y1=y1, x2=x2, y2=y2),
                )
            )
        return detections
