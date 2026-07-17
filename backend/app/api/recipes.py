"""V1 Recipe API。"""

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.exceptions import PermissionDeniedError, RecipeGenerationError, RecipeNotFoundError
from app.core.security import get_current_user
from app.database.session import get_db
from app.entity.db_models import User
from app.entity.recipe_schema import RecipeCreateRequest
from app.entity.schemas import ApiResponse
from app.repositories.recipe_repository import RecipeRepository
from app.services.recipe_service import RecipeService

router = APIRouter(prefix="/api/recipes", tags=["菜谱"])


def get_recipe_service(db: Session = Depends(get_db)) -> RecipeService:
    """与 Food API 共用同一个请求级数据库会话。"""
    return RecipeService(RecipeRepository(db))


def _error(status_code: int, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"code": status_code, "message": message, "data": None},
    )


@router.post("", response_model=ApiResponse, status_code=status.HTTP_201_CREATED)
async def create_recipe(
    body: RecipeCreateRequest,
    current_user: User = Depends(get_current_user),
    service: RecipeService = Depends(get_recipe_service),
):
    try:
        recipe = await service.create_recipe(body, current_user.id)
    except RecipeGenerationError as exc:
        status_code = {
            "RECOGNITION_NOT_FOUND": 404,
            "NO_CONFIRMED_INGREDIENTS": 422,
            "INVALID_LLM_OUTPUT": 422,
            "LLM_UNAVAILABLE": 503,
        }.get(exc.error_code, 500)
        return _error(status_code, exc.message)
    return ApiResponse(code=201, message="菜谱生成成功", data=recipe.model_dump(mode="json"))


@router.get("/{recipe_id}", response_model=ApiResponse)
async def get_recipe(
    recipe_id: int,
    current_user: User = Depends(get_current_user),
    service: RecipeService = Depends(get_recipe_service),
):
    try:
        recipe = await service.get_recipe(recipe_id, current_user.id)
    except RecipeNotFoundError as exc:
        return _error(404, exc.message)
    except PermissionDeniedError as exc:
        return _error(403, exc.message)
    return ApiResponse(data=recipe.model_dump(mode="json"))
