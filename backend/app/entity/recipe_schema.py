"""V1 菜谱与对话接口的数据结构。"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Ingredient(BaseModel):
    name: str = Field(min_length=1)
    amount: float = Field(ge=0)
    unit: str = Field(min_length=1)
    note: str | None = None


class RecipeStep(BaseModel):
    step_no: int = Field(ge=1)
    description: str = Field(min_length=1)
    duration_minutes: int | None = Field(default=None, ge=0)


class NutritionInfo(BaseModel):
    basis: Literal["per_serving"] = "per_serving"
    calories_kcal: float = Field(ge=0)
    protein_g: float = Field(ge=0)
    fat_g: float = Field(ge=0)
    carbohydrates_g: float = Field(ge=0)


class RecipePreferences(BaseModel):
    servings: int = Field(default=2, ge=1, le=10)
    taste: str = Field(default="家常", min_length=1, max_length=20)
    max_time_minutes: int | None = Field(default=None, ge=5, le=180)
    avoid_ingredients: list[str] = Field(default_factory=list)


class RecipeGenerateResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    servings: int = Field(ge=1, le=10)
    cooking_time_minutes: int = Field(ge=1)
    difficulty: str = Field(min_length=1)
    ingredients: list[Ingredient] = Field(min_length=1)
    steps: list[RecipeStep] = Field(min_length=1)
    nutrition: NutritionInfo


class ChatLLMResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: Literal["answer", "update_recipe"]
    answer: str = Field(min_length=1)
    recipe: RecipeGenerateResult | None = None

    @model_validator(mode="after")
    def validate_action_payload(self):
        if self.action == "update_recipe" and self.recipe is None:
            raise ValueError("update_recipe 必须返回完整菜谱")
        if self.action == "answer" and self.recipe is not None:
            raise ValueError("answer 不应返回菜谱")
        return self


class GeneratorInfo(BaseModel):
    provider: str
    model: str
    is_mock: bool


class RecipeResponse(BaseModel):
    recipe_id: int
    recognition_id: int
    version: int
    title: str
    summary: str
    servings: int
    cooking_time_minutes: int
    difficulty: str
    ingredients: list[Ingredient]
    steps: list[RecipeStep]
    nutrition: NutritionInfo
    nutrition_disclaimer: str
    generator: GeneratorInfo
    created_at: datetime
    updated_at: datetime


class RecipeCreateRequest(BaseModel):
    recognition_id: int = Field(gt=0)
    preferences: RecipePreferences = Field(default_factory=RecipePreferences)


class CreateChatSessionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    recipe_id: int = Field(gt=0)


class SendChatMessageRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    content: str = Field(min_length=1, max_length=4000)
