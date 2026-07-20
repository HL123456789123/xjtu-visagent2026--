"""Safe public schemas for Food model package management."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class FoodModelSchema(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        allow_inf_nan=False,
    )


class FoodModelPackageManifest(FoodModelSchema):
    schema_version: Literal[1]
    name: str = Field(min_length=2, max_length=100)
    version: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,99}$")
    task: Literal["detect", "classify"]
    weights_file: Literal["best.pt"]
    classes_file: Literal["classes.yaml"]
    weights_sha256: str = Field(pattern=r"^[a-fA-F0-9]{64}$")
    classes_sha256: str = Field(pattern=r"^[a-fA-F0-9]{64}$")
    class_count: int = Field(strict=True, gt=0, le=10000)
    trained_at: datetime
    dataset: dict[str, Any] | None = None
    metrics: dict[str, float] | None = None

    @field_validator("weights_sha256", "classes_sha256")
    @classmethod
    def normalize_hash(cls, value: str) -> str:
        return value.lower()


class FoodModelClass(FoodModelSchema):
    class_id: int = Field(strict=True, ge=0)
    class_name: str = Field(min_length=1, max_length=100)
    display_name: str = Field(min_length=1, max_length=100)


class FoodModelVersionResponse(FoodModelSchema):
    model_id: int = Field(strict=True, ge=1)
    name: str
    version: str
    task: Literal["detect", "classify"]
    status: Literal["validating", "ready", "active", "failed"]
    is_active: bool
    available: bool
    class_count: int = Field(strict=True, ge=0)
    classes: list[FoodModelClass]
    weight_sha256: str
    classes_sha256: str
    file_size: int = Field(strict=True, ge=0)
    dataset: dict[str, Any] | None = None
    metrics: dict[str, float] | None = None
    validation_error: str | None = None
    created_at: datetime
    validated_at: datetime | None = None
    activated_at: datetime | None = None


class FoodModelListResponse(FoodModelSchema):
    active_model_id: int | None = Field(default=None, strict=True, ge=1)
    items: list[FoodModelVersionResponse]
