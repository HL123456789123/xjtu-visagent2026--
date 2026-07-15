"""
Recipe API 路由（V1 冻结版本）
负责人：陈煜君

接口：
- POST /api/recipes - 生成菜谱（V1 第六节第1点）
- GET /api/recipes/{recipe_id} - 查询菜谱（V1 第六节第2点）
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.logger import get_logger
from app.core.security import get_current_user
from app.core.exceptions import (
    RecipeGenerationError,
    RecipeNotFoundError,
    PermissionDeniedError,
)
from app.database.session import get_db
from app.entity.db_models import User
from app.entity.recipe_schema import RecipeCreateRequest, RecipeResponse
from app.entity.schemas import ApiResponse
from app.services.recipe_service import recipe_service

logger = get_logger("recipe_api")

router = APIRouter(prefix="/api/recipes", tags=["菜谱"])


@router.post(
    "",
    response_model=ApiResponse,
    status_code=status.HTTP_201_CREATED,
    summary="生成菜谱",
    description="根据已确认食材生成菜谱（V1 第六节第1点）",
)
async def create_recipe(
    body: RecipeCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
        生成菜谱

        请求：
        ```json
        {
        "recognition_id": 12,
        "preferences": {
            "servings": 2,
            "taste": "清淡",
            "max_time_minutes": 30,
            "avoid_ingredients": []
        }
        }
        ```
        响应（201）：
        ```json
        {
        "code": 201,
        "message": "菜谱生成成功",
        "data": {
            "recipe_id": 101,
            "recognition_id": 12,
            "version": 1,
            "title": "番茄炒蛋",
            ...
        }
        }
    """

    logger.info(
        f"用户 {current_user.username} (id={current_user.id}) "
        f"请求生成菜谱: recognition_id={body.recognition_id}"
    )

    try:
        recipe = await recipe_service.create_recipe(
            request=body,
            user_id=current_user.id,
        )
        return ApiResponse(
            code=status.HTTP_201_CREATED,
            message="菜谱生成成功",
            data=recipe.model_dump(),
        )

    except RecipeGenerationError as e:
        # V1 第十一节：根据错误码映射 HTTP 状态码
        if e.error_code in ("NO_CONFIRMED_INGREDIENTS", "INVALID_LLM_OUTPUT"):
            logger.warning(f"菜谱生成失败 (422): {e.message}")
            raise HTTPException(status_code=422, detail=e.message)
        elif e.error_code == "LLM_UNAVAILABLE":
            logger.warning(f"LLM 不可用 (503): {e.message}")
            raise HTTPException(status_code=503, detail="智能服务暂时不可用")
        else:
            logger.error(f"未知错误: {e.error_code} - {e.message}")
            raise HTTPException(status_code=500, detail="生成菜谱失败，请稍后重试")
    
    except Exception as e:
        logger.error(f"生成菜谱失败: {e}", exc_info=True)
        raise HTTPException(status_code=503, detail="智能服务暂时不可用")


@router.get(
    "/{recipe_id}",
    response_model=ApiResponse,
    summary="查询菜谱",
    description="根据 ID 查询菜谱详情（V1 第六节第2点）",
)
async def get_recipe(
    recipe_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    查询菜谱

    响应（200）：
    ```json
    {
    "code": 200,
    "message": "success",
    "data": {
        "recipe_id": 101,
        "recognition_id": 12,
        "version": 1,
        "title": "番茄炒蛋",
        ...
    }
    }
    """
    logger.info(
        f"用户 {current_user.username} (id={current_user.id}) "
        f"请求查询菜谱: recipe_id={recipe_id}"
    )

    try:
        recipe = await recipe_service.get_recipe(
            recipe_id=recipe_id,
            user_id=current_user.id,
        )
        return ApiResponse(
            code=status.HTTP_200_OK,
            message="success",
            data=recipe.model_dump(),
        )

    except RecipeNotFoundError as e:
        logger.warning(f"菜谱不存在 (404): {e.message}")
        raise HTTPException(status_code=404, detail=e.message)

    except PermissionDeniedError as e:
        logger.warning(f"权限不足 (403): {e.message}")
        raise HTTPException(status_code=403, detail=e.message)

    except Exception as e:
        logger.error(f"查询菜谱失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="查询菜谱失败，请稍后重试")
