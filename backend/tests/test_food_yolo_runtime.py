from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image

from app.modeling.food_yolo_runtime import (
    BoundingBox,
    FoodModelUnavailableError,
    ModelDetection,
    YoloFoodRecognitionProvider,
)


class FakeScalar:
    def __init__(self, value: float) -> None:
        self.value = value

    def item(self) -> float:
        return self.value


class FakeCoordinates:
    def __init__(self, values: list[float]) -> None:
        self.values = values

    def tolist(self) -> list[float]:
        return self.values


class FakeModel:
    def __init__(self, boxes: list[SimpleNamespace]) -> None:
        self.boxes = boxes
        self.calls: list[dict] = []

    def predict(self, **kwargs):
        self.calls.append(kwargs)
        return [SimpleNamespace(boxes=self.boxes)]


def make_box(class_id: int, confidence: float, coordinates: list[float]) -> SimpleNamespace:
    return SimpleNamespace(
        cls=[FakeScalar(class_id)],
        conf=[FakeScalar(confidence)],
        xyxy=[FakeCoordinates(coordinates)],
    )


@pytest.fixture
def classes_path() -> Path:
    return Path(__file__).resolve().parents[1] / "scripts" / "food_model" / "classes.yaml"


def test_yolo_provider_returns_v1_model_detection_and_reuses_model(
    tmp_path: Path, classes_path: Path
):
    weights = tmp_path / "best.pt"
    image = tmp_path / "food.jpg"
    weights.write_bytes(b"test-only")
    image.write_bytes(b"test-only")
    model = FakeModel([make_box(6, 0.9321, [120.4, 80.2, 310.7, 265.1])])
    load_calls: list[str] = []

    def load_model(path: str) -> FakeModel:
        load_calls.append(path)
        return model

    provider = YoloFoodRecognitionProvider(
        str(weights), str(classes_path), model_loader=load_model
    )

    assert provider.is_available() is True
    expected = [
        ModelDetection(
            class_name="tomato",
            confidence=0.9321,
            bbox=BoundingBox(x1=120.4, y1=80.2, x2=310.7, y2=265.1),
        )
    ]
    assert provider.recognize(str(image)) == expected
    assert provider.recognize(str(image), 0.5) == expected
    assert load_calls == [str(weights)]
    assert [call["conf"] for call in model.calls] == [0.25, 0.5]
    assert all("image_index" not in call for call in model.calls)


def test_yolo_provider_returns_empty_list(tmp_path: Path, classes_path: Path):
    weights = tmp_path / "best.pt"
    image = tmp_path / "empty.jpg"
    weights.write_bytes(b"test-only")
    image.write_bytes(b"test-only")
    provider = YoloFoodRecognitionProvider(
        str(weights), str(classes_path), model_loader=lambda _: FakeModel([])
    )

    assert provider.recognize(str(image)) == []


def test_yolo_provider_reports_missing_weights(tmp_path: Path, classes_path: Path):
    image = tmp_path / "food.jpg"
    image.write_bytes(b"test-only")
    provider = YoloFoodRecognitionProvider(
        str(tmp_path / "missing.pt"), str(classes_path), model_loader=lambda _: FakeModel([])
    )

    assert provider.is_available() is False
    with pytest.raises(FoodModelUnavailableError, match="weights not found"):
        provider.recognize(str(image))


@pytest.mark.parametrize("threshold", [-0.01, 1.01])
def test_yolo_provider_rejects_invalid_threshold(
    tmp_path: Path, classes_path: Path, threshold: float
):
    weights = tmp_path / "best.pt"
    image = tmp_path / "food.jpg"
    weights.write_bytes(b"test-only")
    image.write_bytes(b"test-only")
    provider = YoloFoodRecognitionProvider(
        str(weights), str(classes_path), model_loader=lambda _: FakeModel([])
    )

    with pytest.raises(ValueError, match="conf_threshold"):
        provider.recognize(str(image), threshold)


def test_yolo_provider_rejects_relative_or_missing_image(classes_path: Path, tmp_path: Path):
    weights = tmp_path / "best.pt"
    weights.write_bytes(b"test-only")
    provider = YoloFoodRecognitionProvider(
        str(weights), str(classes_path), model_loader=lambda _: FakeModel([])
    )

    with pytest.raises(ValueError, match="absolute"):
        provider.recognize("food.jpg")


def test_classification_provider_returns_one_full_image_result(tmp_path: Path):
    weights = tmp_path / "best.pt"
    classes = tmp_path / "classes.yaml"
    image = tmp_path / "food.jpg"
    weights.write_bytes(b"test-only")
    classes.write_text(
        "names:\n  0:\n    class_name: tomato\n    display_name: 番茄\n",
        encoding="utf-8",
    )
    Image.new("RGB", (80, 40), color=(200, 30, 30)).save(image, "JPEG")
    model = SimpleNamespace(
        predict=lambda **_: [
            SimpleNamespace(probs=SimpleNamespace(top1=0, top1conf=FakeScalar(0.91)))
        ]
    )
    provider = YoloFoodRecognitionProvider(
        str(weights),
        str(classes),
        task="classify",
        model_loader=lambda _: model,
    )

    assert provider.task == "classify"
    assert provider.localization == "full_image"
    assert provider.recognize(str(image), 0.5) == [
        ModelDetection(
            class_name="tomato",
            confidence=0.91,
            bbox=BoundingBox(x1=0.0, y1=0.0, x2=80.0, y2=40.0),
        )
    ]
