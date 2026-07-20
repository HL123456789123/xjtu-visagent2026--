"""Administrator API for the Food runtime model registry."""

from __future__ import annotations

import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, UploadFile, status
from sqlalchemy.orm import Session

from app.config.settings import Settings
from app.core.security import RequireAdmin
from app.database.session import get_db
from app.entity.db_models import User
from app.entity.schemas import ApiResponse
from app.services.food_model_service import FoodModelService, InvalidFoodModelPackageError

router = APIRouter(prefix="/api/admin/food-models", tags=["Food 模型管理"])


def get_food_model_service(db: Session = Depends(get_db)) -> FoodModelService:
    return FoodModelService(db)


@router.get("", response_model=ApiResponse)
async def list_food_models(
    current_user: User = Depends(RequireAdmin()),
    service: FoodModelService = Depends(get_food_model_service),
):
    del current_user
    data = service.list_versions()
    return ApiResponse(code=200, message="success", data=data.model_dump(mode="json"))


@router.post("", response_model=ApiResponse, status_code=status.HTTP_201_CREATED)
async def upload_food_model(
    package: UploadFile,
    current_user: User = Depends(RequireAdmin()),
    service: FoodModelService = Depends(get_food_model_service),
):
    if Path(package.filename or "").suffix.lower() != ".zip":
        raise InvalidFoodModelPackageError("仅支持标准 ZIP 模型包")
    limit = Settings().FOOD_MODEL_MAX_PACKAGE_BYTES
    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as output:
            temp_path = Path(output.name)
            total = 0
            while chunk := await package.read(1024 * 1024):
                total += len(chunk)
                if total > limit:
                    raise InvalidFoodModelPackageError("模型包不得超过 512 MiB")
                output.write(chunk)
        model = service.register_package(temp_path, current_user)
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)
    return ApiResponse(code=201, message="模型包校验通过", data=model.model_dump(mode="json"))


@router.post("/{model_id}/activate", response_model=ApiResponse)
async def activate_food_model(
    model_id: int,
    current_user: User = Depends(RequireAdmin()),
    service: FoodModelService = Depends(get_food_model_service),
):
    model = service.activate(model_id, current_user)
    return ApiResponse(code=200, message="模型已启用", data=model.model_dump(mode="json"))


@router.post("/rollback", response_model=ApiResponse)
async def rollback_food_model(
    current_user: User = Depends(RequireAdmin()),
    service: FoodModelService = Depends(get_food_model_service),
):
    model = service.rollback(current_user)
    return ApiResponse(code=200, message="已回滚到上一健康模型", data=model.model_dump(mode="json"))


@router.delete("/{model_id}", response_model=ApiResponse)
async def delete_food_model(
    model_id: int,
    current_user: User = Depends(RequireAdmin()),
    service: FoodModelService = Depends(get_food_model_service),
):
    service.delete(model_id, current_user)
    return ApiResponse(code=200, message="模型已删除")
