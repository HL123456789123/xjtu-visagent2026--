"""食物识别接口的数据传输对象。"""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class FoodSchemaBase(BaseModel):
    """食物识别 DTO 的公共配置。"""

    model_config = {"str_strip_whitespace": True}


class BoundingBox(FoodSchemaBase):
    """YOLO 检测框，坐标使用原图像素坐标。"""

    x1: float
    y1: float
    x2: float
    y2: float

    @model_validator(mode="after")
    def validate_coordinate_order(self) -> "BoundingBox":
        """确保检测框具有正面积。"""
        if self.x2 <= self.x1:
            raise ValueError("bbox 坐标必须满足 x2 > x1")
        if self.y2 <= self.y1:
            raise ValueError("bbox 坐标必须满足 y2 > y1")
        return self


class IngredientCandidate(FoodSchemaBase):
    """YOLO 返回的单个食材候选项。"""

    key: str = Field(
        ...,
        min_length=1,
        max_length=100,
        pattern=r"^[a-z0-9][a-z0-9_-]*$",
        description="稳定的英文食材类别键",
    )
    name: str = Field(..., min_length=1, max_length=100, description="中文展示名称")
    confidence: float = Field(..., ge=0, le=1, description="YOLO 置信度")
    bbox: BoundingBox | None = Field(default=None, description="检测框；无定位信息时为空")
    source: Literal["yolo"] = "yolo"


class ConfirmedIngredient(FoodSchemaBase):
    """用户最终确认的食材快照项。"""

    key: str = Field(
        ...,
        min_length=1,
        max_length=100,
        pattern=r"^[a-z0-9][a-z0-9_-]*$",
        description="稳定的英文食材类别键",
    )
    name: str = Field(..., min_length=1, max_length=100, description="中文展示名称")
    quantity: str | None = Field(default=None, max_length=100, description="数量，如“2”或“适量”")
    unit: str | None = Field(default=None, max_length=50, description="单位，如“个”或“克”")
    source: Literal["yolo", "manual"] = Field(..., description="食材来源")


def _validate_unique_ingredient_keys(ingredients: list[ConfirmedIngredient]) -> None:
    keys = [ingredient.key for ingredient in ingredients]
    if len(keys) != len(set(keys)):
        raise ValueError("食材 key 不允许重复")


class ConfirmIngredientsRequest(FoodSchemaBase):
    """完整覆盖识别任务确认食材快照的请求体。"""

    confirmed_ingredients: list[ConfirmedIngredient] = Field(
        ...,
        description="用户确认后的完整食材列表，不能为空",
    )

    @model_validator(mode="after")
    def validate_unique_keys(self) -> "ConfirmIngredientsRequest":
        if not self.confirmed_ingredients:
            raise ValueError("确认食材列表不能为空")
        _validate_unique_ingredient_keys(self.confirmed_ingredients)
        return self


class FoodRecognitionResponse(FoodSchemaBase):
    """食物识别任务对外响应；不包含本地临时文件路径。"""

    recognition_id: str = Field(..., min_length=1, description="识别任务 ID")
    status: str = Field(..., min_length=1, description="recognized 或 confirmed")
    image_object_name: str = Field(..., min_length=1, description="MinIO 对象名")
    provider: Literal["yolo"] = "yolo"
    model_version: str = Field(..., min_length=1)
    conf_threshold: float = Field(..., ge=0, le=1)
    raw_detections: list[IngredientCandidate] = Field(default_factory=list)
    confirmed_ingredients: list[ConfirmedIngredient] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
    confirmed_at: datetime | None = None
