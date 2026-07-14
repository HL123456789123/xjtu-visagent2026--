"""
菜谱相关 Pydantic Schema（冻结版本）
冻结时间：2026-07-10
负责人：陈煜君

Schema 分层原则：
- Create 模型：创建资源时的请求体（仅含识别ID + 偏好）
- Generate 模型：AI 生成菜谱的中间产物（未持久化）
- Response 模型：API 返回的响应体（含数据库字段）
- Update 模型：Agent 更新菜谱的请求体
"""
from datetime import datetime
from enum import Enum
from typing import List, Optional, Union

from pydantic import BaseModel, Field, field_validator


# ══════════════════════════════════════════════════════════════
# 一、枚举类型
# ══════════════════════════════════════════════════════════════

class DifficultyLevel(str, Enum):
    """难度等级"""
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


class CuisineType(str, Enum):
    """菜系类型"""
    CHINESE = "chinese"
    WESTERN = "western"
    JAPANESE = "japanese"
    KOREAN = "korean"
    OTHER = "other"


class RecipeSource(str, Enum):
    """菜谱来源"""
    AI = "ai"
    MANUAL = "manual"


# ══════════════════════════════════════════════════════════════
# 二、食材 Schema
# ══════════════════════════════════════════════════════════════

class Ingredient(BaseModel):
    """食材信息（支持数字和文本两种用量）"""
    name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="食材名称，如：番茄、鸡蛋"
    )
    amount: Optional[float] = Field(
        None,
        gt=0,
        description="用量（数字），如：200、3"
    )
    amount_text: Optional[str] = Field(
        None,
        max_length=20,
        description="用量（文本），如：适量、少许"
    )
    unit: Optional[str] = Field(
        None,
        max_length=20,
        description="单位，如：克、个、毫升"
    )
    category: Optional[str] = Field(
        None,
        max_length=50,
        description="食材分类，如：蔬菜、肉类、调味料"
    )

    @field_validator("amount", "amount_text", mode="before")
    @classmethod
    def validate_at_least_one_amount(cls, v, info):
        """校验至少有一种用量描述方式"""
        values = info.data
        if info.field_name == "amount":
            if v is None and values.get("amount_text") is None:
                raise ValueError("amount 和 amount_text 至少提供一个")
        return v


# ══════════════════════════════════════════════════════════════
# 三、菜谱步骤 Schema
# ══════════════════════════════════════════════════════════════

class RecipeStep(BaseModel):
    """菜谱步骤"""
    step_number: int = Field(
        ...,
        ge=1,
        description="步骤序号，从1开始"
    )
    description: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="步骤描述"
    )
    duration_minutes: Optional[int] = Field(
        None,
        ge=0,
        description="预计耗时（分钟）"
    )
    tips: Optional[str] = Field(
        None,
        max_length=200,
        description="小贴士或注意事项"
    )


# ══════════════════════════════════════════════════════════════
# 四、营养信息 Schema
# ══════════════════════════════════════════════════════════════

class NutritionInfo(BaseModel):
    """
    营养成分（估算值）

    注意：所有数据为 AI 估算值，仅供参考，不构成医学建议
    disclaimer 字段由 Service 层统一填充，不在 Schema 层写死默认值
    """
    calories: float = Field(
        ...,
        ge=0,
        description="卡路里（千卡）"
    )
    protein: float = Field(
        ...,
        ge=0,
        description="蛋白质（克）"
    )
    fat: float = Field(
        ...,
        ge=0,
        description="脂肪（克）"
    )
    carbs: float = Field(
        ...,
        ge=0,
        description="碳水化合物（克）"
    )
    fiber: Optional[float] = Field(
        None,
        ge=0,
        description="膳食纤维（克）"
    )
    disclaimer: str = Field(
        ...,
        description="免责声明，由 Service 层注入"
    )


# ══════════════════════════════════════════════════════════════
# 五、创建菜谱请求
# ══════════════════════════════════════════════════════════════

class RecipeCreate(BaseModel):
    """
    创建菜谱请求

    前端只需传识别任务ID和可选偏好，菜谱内容由后端 Service 生成
    """
    recognition_id: int = Field(
        ...,
        description="关联的识别任务ID"
    )
    preferences: Optional[str] = Field(
        None,
        max_length=500,
        description="用户偏好，如：少油、清淡、不加辣"
    )
    servings: Optional[int] = Field(
        None,
        ge=1,
        le=20,
        description="几人份，不传则使用识别时的默认值或由 AI 决定"
    )


# ══════════════════════════════════════════════════════════════
# 六、AI 生成中间产物（未持久化）
# ══════════════════════════════════════════════════════════════

class RecipeGenerateResult(BaseModel):
    """
    AI 生成的原始菜谱（未持久化）

    不含 id、user_id、created_at 等数据库字段
    供 Service 层校验后转换为 RecipeResponse 入库
    """
    title: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="菜名"
    )
    description: Optional[str] = Field(
        None,
        max_length=1000,
        description="菜谱简介"
    )
    ingredients: List[Ingredient] = Field(
        ...,
        min_length=1,
        description="食材列表"
    )
    steps: List[RecipeStep] = Field(
        ...,
        min_length=1,
        description="步骤列表"
    )
    nutrition: Optional[NutritionInfo] = Field(
        None,
        description="营养信息"
    )
    cuisine: Optional[str] = Field(
        None,
        max_length=50,
        description="菜系"
    )
    difficulty: DifficultyLevel = Field(
        default=DifficultyLevel.MEDIUM,
        description="难度等级"
    )
    prep_time_minutes: int = Field(
        default=0,
        ge=0,
        description="准备时间（分钟）"
    )
    cook_time_minutes: int = Field(
        default=0,
        ge=0,
        description="烹饪时间（分钟）"
    )
    servings: int = Field(
        default=2,
        ge=1,
        description="几人份"
    )

    @field_validator("steps")
    @classmethod
    def validate_step_order(cls, steps: List[RecipeStep]) -> List[RecipeStep]:
        """校验步骤序号连续"""
        if steps:
            expected = 1
            for step in steps:
                if step.step_number != expected:
                    raise ValueError(f"步骤序号不连续，期望 {expected}，实际 {step.step_number}")
                expected += 1
        return steps


# ══════════════════════════════════════════════════════════════
# 七、AI 生成响应（含来源标识）
# ══════════════════════════════════════════════════════════════

class RecipeGenerateResponse(BaseModel):
    """AI 生成菜谱响应"""
    recipe: RecipeGenerateResult = Field(
        ...,
        description="生成的菜谱"
    )
    confidence: float = Field(
        ...,
        ge=0,
        le=1,
        description="置信度（0-1）"
    )
    source: str = Field(
        default="llm",
        description="生成来源：llm / fallback"
    )


# ══════════════════════════════════════════════════════════════
# 八、完整菜谱响应（含数据库字段）
# ══════════════════════════════════════════════════════════════

class RecipeResponse(BaseModel):
    """菜谱完整响应（含数据库生成字段）"""
    id: int = Field(..., description="菜谱ID")
    recognition_id: int = Field(..., description="关联的识别任务ID")
    title: str = Field(..., description="菜名")
    description: Optional[str] = Field(None, description="简介")
    ingredients: List[Ingredient] = Field(..., description="食材列表")
    steps: List[RecipeStep] = Field(..., description="步骤列表")
    nutrition: Optional[NutritionInfo] = Field(None, description="营养信息")
    cuisine: Optional[str] = Field(None, description="菜系")
    difficulty: str = Field(..., description="难度")
    prep_time_minutes: int = Field(..., description="准备时间（分钟）")
    cook_time_minutes: int = Field(..., description="烹饪时间（分钟）")
    servings: int = Field(..., description="几人份")
    image_url: Optional[str] = Field(None, description="封面图URL")
    source: str = Field(default="ai", description="来源：ai/manual")
    version: int = Field(default=1, description="版本号，每次更新+1")
    user_id: int = Field(..., description="创建者ID")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")

    model_config = {"from_attributes": True}


# ══════════════════════════════════════════════════════════════
# 九、Agent 更新菜谱请求
# ══════════════════════════════════════════════════════════════

class RecipeUpdateRequest(BaseModel):
    """
    Agent 修改菜谱的请求

    所有字段均为可选，传入什么字段就更新什么字段
    版本号由 Service 层自动 +1
    """
    title: Optional[str] = Field(None, min_length=1, max_length=200, description="菜名")
    description: Optional[str] = Field(None, max_length=1000, description="简介")
    ingredients: Optional[List[Ingredient]] = Field(None, min_length=1, description="食材列表")
    steps: Optional[List[RecipeStep]] = Field(None, min_length=1, description="步骤列表")
    nutrition: Optional[NutritionInfo] = Field(None, description="营养信息")
    cuisine: Optional[str] = Field(None, max_length=50, description="菜系")
    difficulty: Optional[DifficultyLevel] = Field(None, description="难度等级")
    prep_time_minutes: Optional[int] = Field(None, ge=0, description="准备时间（分钟）")
    cook_time_minutes: Optional[int] = Field(None, ge=0, description="烹饪时间（分钟）")
    servings: Optional[int] = Field(None, ge=1, description="几人份")


# ══════════════════════════════════════════════════════════════
# 十、列表查询响应（分页用）
# ══════════════════════════════════════════════════════════════

class RecipeListResponse(BaseModel):
    """菜谱列表响应"""
    items: List[RecipeResponse] = Field(..., description="菜谱列表")
    total: int = Field(..., description="总数")
    page: int = Field(default=1, ge=1, description="当前页码")
    page_size: int = Field(default=20, ge=1, le=100, description="每页数量")