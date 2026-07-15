"""V1 冻结的同步 Food API。"""

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

FOOD_RECOGNITION_ERROR_RESPONSES = {
    401: {"description": "UNAUTHORIZED"},
    403: {"description": "FORBIDDEN"},
    404: {"description": "RECOGNITION_NOT_FOUND"},
    413: {"description": "IMAGE_TOO_LARGE"},
    415: {"description": "UNSUPPORTED_IMAGE_TYPE"},
    422: {"description": "EMPTY_INGREDIENTS"},
    503: {"description": "FOOD_MODEL_UNAVAILABLE"},
}


def get_food_recognition_service(db: Session = Depends(get_db)) -> FoodRecognitionService:
    """每个请求绑定一个 SQLAlchemy Repository，避免进程内伪持久化。"""
    return FoodRecognitionService(repository=FoodRepository(db))


@router.post(
    "/recognitions",
    response_model=ApiResponse,
    status_code=201,
    responses=FOOD_RECOGNITION_ERROR_RESPONSES,
)
async def create_food_recognition(
    image: UploadFile = File(..., description="单张 JPG、JPEG 或 PNG 图片"),
    conf_threshold: float = Form(0.25, ge=0, le=1, description="模型置信度阈值"),
    current_user: User = Depends(get_current_user),
    service: FoodRecognitionService = Depends(get_food_recognition_service),
):
    """上传一张图，同步识别并返回 V1 候选食材。"""
    recognition = await service.create_recognition(
        user_id=current_user.id,
        image=image,
        conf_threshold=conf_threshold,
    )
    return ApiResponse(code=201, message="识别完成", data=recognition.model_dump(mode="json"))


@router.get(
    "/recognitions/{recognition_id}",
    response_model=ApiResponse,
    responses=FOOD_RECOGNITION_ERROR_RESPONSES,
)
async def get_food_recognition(
    recognition_id: int,
    current_user: User = Depends(get_current_user),
    service: FoodRecognitionService = Depends(get_food_recognition_service),
):
    """读取当前用户的一条识别记录和确认快照。"""
    recognition = service.get_recognition(
        user_id=current_user.id,
        recognition_id=recognition_id,
    )
    return ApiResponse(code=200, message="success", data=recognition.model_dump(mode="json"))


@router.put(
    "/recognitions/{recognition_id}/ingredients",
    response_model=ApiResponse,
    responses=FOOD_RECOGNITION_ERROR_RESPONSES,
)
async def confirm_food_ingredients(
    recognition_id: int,
    request: ConfirmIngredientsRequest,
    current_user: User = Depends(get_current_user),
    service: FoodRecognitionService = Depends(get_food_recognition_service),
):
    """用请求中的完整 ingredients 数组覆盖旧确认快照。"""
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


@file_router.get("/food/{recognition_id}", responses=FOOD_RECOGNITION_ERROR_RESPONSES)
async def get_food_image(
    recognition_id: int,
    current_user: User = Depends(get_current_user),
    service: FoodRecognitionService = Depends(get_food_recognition_service),
):
    """供 V1 ``image_url`` 使用的受认证保护原图读取接口。"""
    content, media_type = await service.get_image(
        user_id=current_user.id,
        recognition_id=recognition_id,
    )
    return Response(content=content, media_type=media_type)
