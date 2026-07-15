"""食物识别模块 V1 冻结契约的数据传输对象。"""

import math
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


class FoodSchemaBase(BaseModel):
    """Food DTO 的公共校验设置。"""

    model_config = {"str_strip_whitespace": True, "allow_inf_nan": False}


class BoundingBox(FoodSchemaBase):
    """原图像素坐标的检测框。"""

    x1: float
    y1: float
    x2: float
    y2: float

    @field_validator("x1", "y1", "x2", "y2")
    @classmethod
    def validate_finite_coordinate(cls, value: float) -> float:
        if not math.isfinite(value):
            raise ValueError("bbox 坐标必须是有限数值")
        return value

    @model_validator(mode="after")
    def validate_coordinate_order(self) -> "BoundingBox":
        if self.x2 <= self.x1 or self.y2 <= self.y1:
            raise ValueError("bbox 坐标必须满足 x2 > x1 且 y2 > y1")
        return self


class ModelDetection(FoodSchemaBase):
    """黄小石模型接口固定输出，不含中文名和数据库信息。"""

    class_name: str = Field(..., min_length=1, max_length=100, pattern=r"^[a-z0-9][a-z0-9_-]*$")
    confidence: float = Field(..., ge=0, le=1)
    bbox: BoundingBox

    @field_validator("class_name", mode="before")
    @classmethod
    def normalize_class_name(cls, value: str) -> str:
        if not isinstance(value, str):
            return value
        return value.strip().lower().replace(" ", "_")

    @field_validator("confidence")
    @classmethod
    def validate_finite_confidence(cls, value: float) -> float:
        if not math.isfinite(value):
            raise ValueError("置信度必须是有限数值")
        return value


class IngredientCandidate(FoodSchemaBase):
    """Food API 返回给前端的候选食材。"""

    candidate_id: str = Field(..., min_length=1, max_length=100)
    class_name: str = Field(..., min_length=1, max_length=100)
    display_name: str = Field(..., min_length=1, max_length=100)
    confidence: float = Field(..., ge=0, le=1)
    bbox: BoundingBox
    source: Literal["model", "manual"] = "model"

    @field_validator("class_name", mode="before")
    @classmethod
    def normalize_class_name(cls, value: str) -> str:
        if not isinstance(value, str):
            return value
        return value.strip().lower().replace(" ", "_")


class ConfirmedIngredient(FoodSchemaBase):
    """用户确认后的最终食材快照。"""

    name: str = Field(..., min_length=1, max_length=100)
    class_name: str | None = Field(default=None, max_length=100)
    quantity: int = Field(..., ge=1, le=100000)
    unit: str = Field(..., min_length=1, max_length=50)
    source: Literal["model", "manual"]

    @field_validator("class_name", mode="before")
    @classmethod
    def normalize_class_name(cls, value: str | None) -> str | None:
        if value is None or not isinstance(value, str):
            return value
        normalized = value.strip().lower().replace(" ", "_")
        return normalized or None


class ConfirmIngredientsRequest(FoodSchemaBase):
    """V1 确认食材请求，数组将完整覆盖旧快照。"""

    ingredients: list[ConfirmedIngredient]

    @model_validator(mode="after")
    def validate_ingredients_not_empty(self) -> "ConfirmIngredientsRequest":
        if not self.ingredients:
            raise ValueError("食材不能为空")
        return self


class FoodRecognitionCreateData(FoodSchemaBase):
    recognition_id: int
    status: Literal["completed"]
    provider: Literal["mock", "yolo"]
    model_version: str
    image_url: str
    ingredients: list[IngredientCandidate]
    created_at: datetime


class FoodRecognitionDetailData(FoodRecognitionCreateData):
    confirmed_ingredients: list[ConfirmedIngredient]
    updated_at: datetime


class ConfirmIngredientsData(FoodSchemaBase):
    recognition_id: int
    confirmed_ingredients: list[ConfirmedIngredient]
    confirmed_at: datetime
