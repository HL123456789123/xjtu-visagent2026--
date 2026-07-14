"""面向 YOLO 运行时的食物识别 Provider 契约。"""
from typing import Protocol, runtime_checkable

from app.core.exceptions import AppException
from app.entity.food_schemas import IngredientCandidate


class FoodRecognitionProviderError(AppException):
    """YOLO Provider 无法提供有效结果时的领域异常。"""

    def __init__(self, message: str = "食物识别模型服务不可用", detail: str | None = None):
        super().__init__(code=503, message=message, detail=detail)


class FoodRecognitionProviderUnavailable(FoodRecognitionProviderError):
    """YOLO 权重或运行时尚不可用。"""


class FoodRecognitionInferenceError(FoodRecognitionProviderError):
    """YOLO 推理执行失败。"""


class FoodRecognitionInvalidResultError(FoodRecognitionProviderError):
    """YOLO 返回的数据不符合食物识别 DTO。"""


@runtime_checkable
class FoodRecognitionProvider(Protocol):
    """可替换的 YOLO 运行时边界。

    真实运行时和测试中的 Fake Provider 都必须实现此接口；生产代码不存在
    Mock/YOLO 模式切换。
    """

    model_version: str

    async def recognize(
        self,
        image_path: str,
        conf_threshold: float,
    ) -> list[IngredientCandidate]:
        """识别一张本地临时图片并返回候选食材。"""


class YoloFoodRecognitionProvider:
    """YOLO Provider 占位实现。

    Day 1 不加载权重。模型运行时负责人接入后仅需实现 ``recognize``，并在
    组装 ``FoodRecognitionService`` 时注入该实例。
    """

    model_version = "yolo-unconfigured"

    async def recognize(
        self,
        image_path: str,
        conf_threshold: float,
    ) -> list[IngredientCandidate]:
        raise FoodRecognitionProviderUnavailable(
            "YOLO 食物识别运行时尚未接入",
            detail="请注入已加载食物类别权重的 YoloFoodRecognitionProvider 实现",
        )
