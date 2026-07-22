"""Authenticated V1 Recipe API."""

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.database.session import get_db
from app.entity.db_models import User
from app.entity.recipe_schemas import RecipeCreateRequest
from app.entity.schemas import ApiResponse
from app.repositories.food_repository import FoodRepository
from app.repositories.recipe_repository import RecipeRepository
from app.services.recipe_service import RecipeService

router = APIRouter(prefix="/api/recipes", tags=["菜谱"])


def get_recipe_service(db: Session = Depends(get_db)) -> RecipeService:
    return RecipeService(FoodRepository(db), RecipeRepository(db))


@router.post("", response_model=ApiResponse, status_code=status.HTTP_201_CREATED)
async def create_recipe(
    request: RecipeCreateRequest,
    current_user: User = Depends(get_current_user),
    service: RecipeService = Depends(get_recipe_service),
):
    recipe = await service.create_recipe(request, current_user.id)
    return ApiResponse(code=201, message="菜谱生成成功", data=recipe.model_dump(mode="json"))


@router.get("/{recipe_id}", response_model=ApiResponse)
async def get_recipe(
    recipe_id: int,
    current_user: User = Depends(get_current_user),
    service: RecipeService = Depends(get_recipe_service),
):
    recipe = await service.get_recipe(recipe_id, current_user.id)
    return ApiResponse(code=200, message="success", data=recipe.model_dump(mode="json"))
