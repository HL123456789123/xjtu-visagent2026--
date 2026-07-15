from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field


# 食材（V1 第三节第4点）
class Ingredient(BaseModel):
    name: str
    amount: float
    unit: str
    note: Optional[str] = None


# 步骤（V1 第七节第3点）
class RecipeStep(BaseModel):
    step_no: int
    description: str
    duration_minutes: Optional[int] = None


# 营养（V1 第七节第3点）
class NutritionInfo(BaseModel):
    basis: str = "per_serving"
    calories_kcal: float
    protein_g: float
    fat_g: float
    carbohydrates_g: float


# 用户偏好（V1 第三节第5点）
class RecipePreferences(BaseModel):
    servings: int = Field(default=2, ge=1, le=10)
    taste: str = Field(default="家常", max_length=20)
    max_time_minutes: Optional[int] = Field(None, ge=5, le=180)
    avoid_ingredients: List[str] = []


# LLM 生成输出（V1 第七节第3点）
class RecipeGenerateResult(BaseModel):
    title: str
    summary: str
    servings: int
    cooking_time_minutes: int
    difficulty: str
    ingredients: List[Ingredient]
    steps: List[RecipeStep]
    nutrition: NutritionInfo


# 生成器信息（V1 第七节第1点）
class GeneratorInfo(BaseModel):
    provider: str
    model: str
    is_mock: bool


# API 响应（V1 第六节第1点）
class RecipeResponse(BaseModel):
    recipe_id: int
    recognition_id: int
    version: int
    title: str
    summary: str
    servings: int
    cooking_time_minutes: int
    difficulty: str
    ingredients: List[Ingredient]
    steps: List[RecipeStep]
    nutrition: NutritionInfo
    nutrition_disclaimer: str
    generator: GeneratorInfo
    created_at: datetime
    updated_at: datetime


# 创建请求（V1 第六节第1点）
class RecipeCreateRequest(BaseModel):
    recognition_id: int
    preferences: RecipePreferences = Field(default_factory=RecipePreferences)