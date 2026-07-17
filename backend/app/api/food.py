"""Authenticated V1.1 multi-image Food API."""

from fastapi import APIRouter, Depends, File, Form, UploadFile
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.database.session import get_db
from app.entity.db_models import User
from app.entity.food_schemas import ConfirmIngredientsRequest
from app.entity.schemas import ApiResponse
from app.repositories.food_repository import FoodRepository
from app.services.food_recognition_service import FoodRecognitionService

router = APIRouter(prefix="/api/food", tags=["食物识别"])
file_router = APIRouter(prefix="/api/files", tags=["文件"])

FOOD_ERROR_RESPONSES = {
    400: {"description": "BAD_REQUEST / INVALID_IMAGE_COUNT"},
    401: {"description": "UNAUTHORIZED"},
    403: {"description": "FORBIDDEN"},
    404: {"description": "RECOGNITION_NOT_FOUND"},
    413: {"description": "IMAGE_TOO_LARGE / IMAGE_BATCH_TOO_LARGE"},
    415: {"description": "UNSUPPORTED_IMAGE_TYPE"},
    422: {"description": "INVALID_IMAGE_CONTENT / EMPTY_INGREDIENTS"},
    503: {"description": "FOOD_MODEL_UNAVAILABLE"},
}


def get_food_recognition_service(db: Session = Depends(get_db)) -> FoodRecognitionService:
    return FoodRecognitionService(repository=FoodRepository(db))


@router.post(
    "/recognitions",
    response_model=ApiResponse,
    status_code=201,
    responses=FOOD_ERROR_RESPONSES,
)
async def create_food_recognition(
    images: list[UploadFile] | None = File(
        default=None,
        description="唯一上传字段；按顺序提交 1 至 5 张 JPG、JPEG 或 PNG 图片",
    ),
    conf_threshold: float = Form(0.25, ge=0, le=1),
    current_user: User = Depends(get_current_user),
    service: FoodRecognitionService = Depends(get_food_recognition_service),
):
    recognition = await service.create_recognition(
        user_id=current_user.id,
        images=images or [],
        conf_threshold=conf_threshold,
    )
    return ApiResponse(code=201, message="识别完成", data=recognition.model_dump(mode="json"))


@router.get(
    "/recognitions/{recognition_id}",
    response_model=ApiResponse,
    responses=FOOD_ERROR_RESPONSES,
)
async def get_food_recognition(
    recognition_id: int,
    current_user: User = Depends(get_current_user),
    service: FoodRecognitionService = Depends(get_food_recognition_service),
):
    recognition = service.get_recognition(
        user_id=current_user.id,
        recognition_id=recognition_id,
    )
    return ApiResponse(code=200, message="success", data=recognition.model_dump(mode="json"))


@router.put(
    "/recognitions/{recognition_id}/ingredients",
    response_model=ApiResponse,
    responses=FOOD_ERROR_RESPONSES,
)
async def confirm_food_ingredients(
    recognition_id: int,
    request: ConfirmIngredientsRequest,
    current_user: User = Depends(get_current_user),
    service: FoodRecognitionService = Depends(get_food_recognition_service),
):
    confirmation = service.confirm_ingredients(
        user_id=current_user.id,
        recognition_id=recognition_id,
        ingredients=request.ingredients,
    )
    return ApiResponse(
        code=200,
        message="食材已确认",
        data=confirmation.model_dump(mode="json"),
    )


@file_router.get(
    "/food/{recognition_id}/{image_index}",
    responses=FOOD_ERROR_RESPONSES,
)
async def get_food_image(
    recognition_id: int,
    image_index: int,
    current_user: User = Depends(get_current_user),
    service: FoodRecognitionService = Depends(get_food_recognition_service),
):
    content, media_type = await service.get_image(
        user_id=current_user.id,
        recognition_id=recognition_id,
        image_index=image_index,
    )
    return Response(content=content, media_type=media_type)
