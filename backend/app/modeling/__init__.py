"""Model runtime adapters used by application services."""

from app.modeling.food_yolo_runtime import (
    BoundingBox,
    FoodModelUnavailableError,
    FoodRecognitionProvider,
    ModelDetection,
    YoloFoodRecognitionProvider,
)

__all__ = [
    "BoundingBox",
    "FoodModelUnavailableError",
    "FoodRecognitionProvider",
    "ModelDetection",
    "YoloFoodRecognitionProvider",
]
