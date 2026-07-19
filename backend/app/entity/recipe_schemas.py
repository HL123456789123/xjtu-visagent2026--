"""Strict V1 Recipe, Chat, LLM, and SSE boundary schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictSchema(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, allow_inf_nan=False)


class RecipeIngredient(StrictSchema):
    name: str = Field(min_length=1)
    amount: float = Field(ge=0)
    unit: str = Field(min_length=1)
    note: str | None = None


class RecipeStep(StrictSchema):
    step_no: int = Field(strict=True, ge=1)
    description: str = Field(min_length=1)
    duration_minutes: int | None = Field(default=None, strict=True, ge=0)


class NutritionInfo(StrictSchema):
    basis: Literal["per_serving"] = "per_serving"
    calories_kcal: float = Field(ge=0)
    protein_g: float = Field(ge=0)
    fat_g: float = Field(ge=0)
    carbohydrates_g: float = Field(ge=0)


class RecipePreferences(StrictSchema):
    servings: int = Field(default=2, strict=True, ge=1, le=10)
    taste: str = Field(default="家常", min_length=1, max_length=20)
    max_time_minutes: int | None = Field(default=None, strict=True, ge=5, le=180)
    avoid_ingredients: list[str] = Field(default_factory=list)


class RecipeGenerateResult(StrictSchema):
    """The only JSON shape an LLM may return; backend-owned fields are forbidden."""

    title: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    servings: int = Field(strict=True, ge=1, le=10)
    cooking_time_minutes: int = Field(strict=True, ge=1)
    difficulty: str = Field(min_length=1)
    ingredients: list[RecipeIngredient] = Field(min_length=1)
    steps: list[RecipeStep] = Field(min_length=1)
    nutrition: NutritionInfo


class ChatLLMResult(StrictSchema):
    action: Literal["answer", "update_recipe"]
    answer: str = Field(min_length=1)
    recipe: RecipeGenerateResult | None = None

    @model_validator(mode="after")
    def validate_action_payload(self) -> "ChatLLMResult":
        if self.action == "update_recipe" and self.recipe is None:
            raise ValueError("update_recipe must include a complete recipe")
        if self.action == "answer" and self.recipe is not None:
            raise ValueError("answer must not include a recipe")
        return self


class GeneratorInfo(StrictSchema):
    provider: str
    model: str
    is_mock: bool


class RecipeResponse(StrictSchema):
    recipe_id: int = Field(strict=True)
    recognition_id: int = Field(strict=True)
    version: int = Field(strict=True, ge=1)
    title: str
    summary: str
    servings: int = Field(strict=True)
    cooking_time_minutes: int = Field(strict=True)
    difficulty: str
    ingredients: list[RecipeIngredient]
    steps: list[RecipeStep]
    nutrition: NutritionInfo
    nutrition_disclaimer: str
    generator: GeneratorInfo
    created_at: datetime
    updated_at: datetime


class RecipeCreateRequest(StrictSchema):
    recognition_id: int = Field(strict=True, gt=0)
    preferences: RecipePreferences = Field(default_factory=RecipePreferences)


class CreateChatSessionRequest(StrictSchema):
    recipe_id: int = Field(strict=True, gt=0)


class SendChatMessageRequest(StrictSchema):
    content: str = Field(min_length=1, max_length=4000)


class ChatSessionSummary(StrictSchema):
    session_id: int = Field(strict=True)
    recipe_id: int = Field(strict=True)
    title: str | None = None
    message_count: int = Field(strict=True, ge=0)
    last_message_at: datetime | None = None
    created_at: datetime


class ChatMessageResponse(StrictSchema):
    message_id: int = Field(strict=True)
    role: Literal["user", "assistant"]
    content: str
    created_at: datetime


class RecipeHistoryItem(StrictSchema):
    recipe_id: int = Field(strict=True)
    recognition_id: int = Field(strict=True)
    title: str
    version: int = Field(strict=True, ge=1)
    provider: str
    model_version: str
    image_count: int = Field(strict=True, ge=0)
    confirmed_ingredients: list[dict]
    updated_at: datetime
    latest_session: ChatSessionSummary | None = None


class RecipeHistoryPage(StrictSchema):
    items: list[RecipeHistoryItem]
    total: int = Field(strict=True, ge=0)
    page: int = Field(strict=True, ge=1)
    page_size: int = Field(strict=True, ge=1)
