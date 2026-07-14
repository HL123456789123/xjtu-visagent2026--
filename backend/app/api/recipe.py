"""
菜谱模块 API 路由

接口（符合计划 API 契约）：
- POST   /api/recipes          从识别记录生成菜谱（主入口）
- GET    /api/recipes/{id}     获取菜谱详情
- PUT    /api/recipes/{id}     Agent 更新菜谱（供内部调用）

注意：
- 所有接口需要用户认证
- 菜谱生成由 Service 层自动处理（LLM 或降级）
- 前端只需传 recognition_id，不需要传食材列表
"""
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any

from app.core.exceptions import (
    PermissionDeniedError,
    RecipeGenerationError,
    RecipeNotFoundError,
)
from app.core.logger import get_logger
from app.core.security import get_current_user
from app.database.session import get_db
from app.entity.db_models import User
from app.entity.recipe_schemas import (
    ApiResponse,
    RecipeCreate,
    RecipeResponse,
    RecipeUpdateRequest,
)
from app.services.recipe_service import recipe_service

logger = get_logger("recipe_api")

router = APIRouter(prefix="/api/recipes", tags=["菜谱管理"])


# ══════════════════════════════════════════════════════════════
# 一、请求/响应模型（API 层专用，符合计划契约）
# ══════════════════════════════════════════════════════════════

class CreateRecipeRequest(BaseModel):
    """创建菜谱请求（符合计划 API 契约）"""
    recognition_id: int
    preferences: Optional[str] = None
    servings: Optional[int] = None


class UpdateRecipeRequest(BaseModel):
    """更新菜谱请求（Agent 调用）"""
    title: Optional[str] = None
    description: Optional[str] = None
    ingredients: Optional[List[Ingredient]] = None
    steps: Optional[List[RecipeStep]] = None
    nutrition: Optional[NutritionInfo] = None
    cuisine: Optional[str] = None
    difficulty: Optional[str] = None
    prep_time_minutes: Optional[int] = None
    cook_time_minutes: Optional[int] = None
    servings: Optional[int] = None


# ══════════════════════════════════════════════════════════════
# 二、API 路由
# ══════════════════════════════════════════════════════════════

@router.post(
    "/",
    response_model=ApiResponse[RecipeResponse],
    status_code=status.HTTP_201_CREATED,
    summary="从识别记录生成菜谱",
    description="传入 recognition_id，后端自动调用 LLM 或降级生成菜谱并入库",
)
async def create_recipe_from_recognition(
    request: CreateRecipeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    从识别记录生成菜谱（主入口）

    流程：
    1. 校验 recognition_id 属于当前用户
    2. 获取确认后的食材列表
    3. 调用 LLM 生成菜谱（失败则走降级）
    4. 校验结构、入库、返回
    """
    logger.info(
        f"用户 {current_user.username} (id={current_user.id}) "
        f"请求从识别记录 {request.recognition_id} 生成菜谱"
    )

    try:
        result = await recipe_service.create_recipe_from_recognition(
            recognition_id=request.recognition_id,
            user_id=current_user.id,
            preferences=request.preferences,
            servings=request.servings,
        )
        return ApiResponse(
            code=status.HTTP_201_CREATED,
            message="菜谱生成成功",
            data=result,
        )
    except RecipeNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except PermissionDeniedError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except RecipeGenerationError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.error(f"生成菜谱失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="生成菜谱失败，请稍后重试")


@router.get(
    "/{recipe_id}",
    response_model=ApiResponse[RecipeResponse],
    summary="获取菜谱详情",
    description="获取指定菜谱的完整信息，自动校验所有权",
)
async def get_recipe(
    recipe_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取菜谱详情"""
    logger.info(
        f"用户 {current_user.username} (id={current_user.id}) "
        f"请求获取菜谱 {recipe_id}"
    )

    try:
        result = await recipe_service.get_recipe_for_user(
            recipe_id=recipe_id,
            user_id=current_user.id,
        )
        return ApiResponse(
            code=status.HTTP_200_OK,
            message="获取成功",
            data=result,
        )
    except RecipeNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except PermissionDeniedError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        logger.error(f"获取菜谱失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="获取菜谱失败")


@router.put(
    "/{recipe_id}",
    response_model=ApiResponse[RecipeResponse],
    summary="更新菜谱（Agent 调用）",
    description="Agent 修改菜谱，传入要更新的字段，版本号自动 +1",
)
async def update_recipe(
    recipe_id: int,
    request: UpdateRecipeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    更新菜谱（供 Agent 调用）

    支持部分更新，只传入需要修改的字段。
    版本号由 Service 层自动递增。
    """
    logger.info(
        f"用户 {current_user.username} (id={current_user.id}) "
        f"请求更新菜谱 {recipe_id}"
    )

    try:
        result = await recipe_service.update_recipe_for_user(
            recipe_id=recipe_id,
            user_id=current_user.id,
            update_data=request.model_dump(exclude_none=True),
        )
        return ApiResponse(
            code=status.HTTP_200_OK,
            message="菜谱更新成功",
            data=result,
        )
    except RecipeNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except PermissionDeniedError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except RecipeGenerationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"更新菜谱失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="更新菜谱失败")


@router.get(
    "/",
    response_model=ApiResponse[Dict[str, Any]],
    summary="获取菜谱列表",
    description="分页获取当前用户的菜谱列表",
)
async def list_recipes(
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取当前用户的菜谱列表"""
    logger.info(
        f"用户 {current_user.username} (id={current_user.id}) "
        f"请求菜谱列表: page={page}, page_size={page_size}"
    )

    try:
        result = await recipe_service.list_recipes_for_user(
            user_id=current_user.id,
            page=page,
            page_size=min(page_size, 100),
        )
        return ApiResponse(
            code=status.HTTP_200_OK,
            message="获取成功",
            data=result,
        )
    except Exception as e:
        logger.error(f"获取菜谱列表失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="获取菜谱列表失败")


@router.delete(
    "/{recipe_id}",
    response_model=ApiResponse[None],
    summary="删除菜谱",
    description="软删除菜谱（仅标记删除，不物理删除）",
)
async def delete_recipe(
    recipe_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """删除菜谱（软删除）"""
    logger.info(
        f"用户 {current_user.username} (id={current_user.id}) "
        f"请求删除菜谱 {recipe_id}"
    )

    try:
        await recipe_service.delete_recipe_for_user(
            recipe_id=recipe_id,
            user_id=current_user.id,
        )
        return ApiResponse(
            code=status.HTTP_200_OK,
            message="菜谱已删除",
            data=None,
        )
    except RecipeNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except PermissionDeniedError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        logger.error(f"删除菜谱失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="删除菜谱失败")