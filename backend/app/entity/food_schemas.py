"""Strict public DTOs for the V1.1 multi-image Food API."""

from __future__ import annotations

import math
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


class FoodSchemaBase(BaseModel):
    model_config = {
        "extra": "forbid",
        "str_strip_whitespace": True,
        "allow_inf_nan": False,
    }


class BoundingBox(FoodSchemaBase):
    x1: float
    y1: float
    x2: float
    y2: float

    @field_validator("x1", "y1", "x2", "y2")
    @classmethod
    def validate_finite_coordinate(cls, value: float) -> float:
        if not math.isfinite(value):
            raise ValueError("bbox coordinates must be finite")
        return value

    @model_validator(mode="after")
    def validate_coordinate_order(self) -> "BoundingBox":
        if self.x2 <= self.x1 or self.y2 <= self.y1:
            raise ValueError("bbox must satisfy x2 > x1 and y2 > y1")
        return self


class IngredientCandidate(FoodSchemaBase):
    candidate_id: str = Field(min_length=1, max_length=100)
    image_index: int = Field(strict=True, ge=0)
    class_name: str = Field(min_length=1, max_length=100)
    display_name: str = Field(min_length=1, max_length=100)
    confidence: float = Field(ge=0, le=1)
    bbox: BoundingBox
    source: Literal["model", "manual"] = "model"


class RecognitionImage(FoodSchemaBase):
    image_index: int = Field(strict=True, ge=0)
    image_url: str = Field(min_length=1)


class ConfirmedIngredient(FoodSchemaBase):
    name: str = Field(min_length=1, max_length=100)
    class_name: str | None = Field(default=None, max_length=100)
    quantity: int = Field(strict=True, ge=1, le=100000)
    unit: str = Field(min_length=1, max_length=50)
    source: Literal["model", "manual"]

    @field_validator("class_name", mode="before")
    @classmethod
    def normalize_class_name(cls, value: str | None) -> str | None:
        if value is None or not isinstance(value, str):
            return value
        normalized = value.strip().lower().replace(" ", "_")
        return normalized or None


class ConfirmIngredientsRequest(FoodSchemaBase):
    ingredients: list[ConfirmedIngredient]

    @model_validator(mode="after")
    def validate_not_empty(self) -> "ConfirmIngredientsRequest":
        if not self.ingredients:
            raise ValueError("ingredients must not be empty")
        return self


class FoodRecognitionCreateData(FoodSchemaBase):
    recognition_id: int = Field(strict=True)
    status: Literal["completed"]
    provider: Literal["mock", "yolo"]
    model_version: str
    images: list[RecognitionImage] = Field(min_length=1, max_length=5)
    ingredients: list[IngredientCandidate]
    created_at: datetime


class FoodRecognitionDetailData(FoodRecognitionCreateData):
    confirmed_ingredients: list[ConfirmedIngredient]
    updated_at: datetime


class ConfirmIngredientsData(FoodSchemaBase):
    recognition_id: int = Field(strict=True)
    confirmed_ingredients: list[ConfirmedIngredient]
    confirmed_at: datetime


class FoodModelClass(FoodSchemaBase):
    class_name: str = Field(min_length=1, max_length=100)
    display_name: str = Field(min_length=1, max_length=100)


class FoodModelStatusData(FoodSchemaBase):
    provider: Literal["mock", "yolo"]
    model_version: str
    available: bool
    class_count: int = Field(strict=True, ge=0)
    classes: list[FoodModelClass]
