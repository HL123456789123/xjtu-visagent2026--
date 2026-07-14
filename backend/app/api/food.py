"""食物识别 API 路由骨架（由应用入口后续显式注册）。"""
from fastapi import APIRouter, Depends, File, Form, UploadFile

from app.core.security import get_current_user
from app.entity.db_models import User
from app.entity.food_schemas import ConfirmIngredientsRequest
from app.entity.schemas import ApiResponse
from app.services.food_recognition_service import (
    FoodRecognitionService,
    food_recognition_service,
)

router = APIRouter(prefix="/api/food", tags=["食物识别"])

FOOD_RECOGNITION_ERROR_RESPONSES = {
    401: {"description": "未登录、登录凭据无效或已过期"},
    403: {"description": "当前用户无权访问该识别任务"},
    404: {"description": "识别任务不存在"},
    422: {"description": "上传文件、阈值或确认食材参数不符合契约"},
    503: {"description": "MinIO 或 YOLO 食物识别服务不可用"},
}


def get_food_recognition_service() -> FoodRecognitionService:
    """保留服务替换入口，供测试和 ORM/YOLO 接线时注入。"""
    return food_recognition_service


@router.post(
    "/recognitions",
    response_model=ApiResponse,
    status_code=201,
    responses=FOOD_RECOGNITION_ERROR_RESPONSES,
)
async def create_food_recognition(
    image: UploadFile = File(..., description="单张 JPG 或 PNG 食物图片"),
    conf_threshold: float = Form(0.25, ge=0, le=1, description="YOLO 置信度阈值"),
    current_user: User = Depends(get_current_user),
    service: FoodRecognitionService = Depends(get_food_recognition_service),
):
    """上传一张图片，保存原图并返回 YOLO 食材候选项。"""
    recognition = await service.create_recognition(
        user_id=current_user.id,
        image=image,
        conf_threshold=conf_threshold,
    )
    return ApiResponse(
        code=201,
        message="食物识别完成",
        data=recognition.model_dump(mode="json"),
    )


@router.get(
    "/recognitions/{recognition_id}",
    response_model=ApiResponse,
    responses=FOOD_RECOGNITION_ERROR_RESPONSES,
)
async def get_food_recognition(
    recognition_id: str,
    current_user: User = Depends(get_current_user),
    service: FoodRecognitionService = Depends(get_food_recognition_service),
):
    """查询当前用户的一条食物识别任务。"""
    recognition = await service.get_recognition(
        user_id=current_user.id,
        recognition_id=recognition_id,
    )
    return ApiResponse(data=recognition.model_dump(mode="json"))


@router.put(
    "/recognitions/{recognition_id}/confirmed-ingredients",
    response_model=ApiResponse,
    responses=FOOD_RECOGNITION_ERROR_RESPONSES,
)
async def confirm_food_ingredients(
    recognition_id: str,
    request: ConfirmIngredientsRequest,
    current_user: User = Depends(get_current_user),
    service: FoodRecognitionService = Depends(get_food_recognition_service),
):
    """完整覆盖确认食材快照，菜谱模块仅可读取该快照。"""
    recognition = await service.confirm_ingredients(
        user_id=current_user.id,
        recognition_id=recognition_id,
        confirmed_ingredients=request.confirmed_ingredients,
    )
    return ApiResponse(
        message="确认食材已保存",
        data=recognition.model_dump(mode="json"),
    )
