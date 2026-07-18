"""Authenticated V1.1 multi-image Food API."""

import re

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile
from fastapi.responses import Response
from starlette.datastructures import UploadFile as StarletteUploadFile
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

DEFAULT_CONF_THRESHOLD = 0.25
_MULTIPART_BOUNDARY_PATTERN = re.compile(
    r'boundary=(?:"([^"]+)"|([^;\s]+))', re.IGNORECASE
)

FOOD_UPLOAD_OPENAPI = {
    "requestBody": {
        "required": True,
        "content": {
            "multipart/form-data": {
                "schema": {
                    "type": "object",
                    "required": ["images"],
                    "properties": {
                        "images": {
                            "type": "array",
                            "items": {"type": "string", "format": "binary"},
                        },
                        "conf_threshold": {
                            "type": "number",
                            "minimum": 0,
                            "maximum": 1,
                            "default": DEFAULT_CONF_THRESHOLD,
                        },
                    },
                }
            }
        },
    }
}


def get_food_recognition_service(db: Session = Depends(get_db)) -> FoodRecognitionService:
    return FoodRecognitionService(repository=FoodRepository(db))


def _is_empty_multipart_body(content_type: str, body: bytes) -> bool:
    """Recognize only an intentionally fieldless multipart payload as zero images."""
    if "multipart/form-data" not in content_type.lower():
        return False
    match = _MULTIPART_BOUNDARY_PATTERN.search(content_type)
    if match is None:
        return False
    boundary = (match.group(1) or match.group(2)).encode("utf-8")
    normalized_body = body.strip()
    return not normalized_body or normalized_body == b"--" + boundary + b"--"


def _parse_conf_threshold(value: object) -> float:
    if value is None:
        return DEFAULT_CONF_THRESHOLD
    try:
        parsed = float(str(value))
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail="conf_threshold must be a number") from exc
    if not 0 <= parsed <= 1:
        raise HTTPException(status_code=422, detail="conf_threshold must be between 0 and 1")
    return parsed


async def _read_food_upload(request: Request) -> tuple[list[UploadFile], float]:
    """Parse the only public multipart field without losing a zero-image request.

    FastAPI's File dependency rejects a fieldless multipart body before the route
    executes. Parsing here lets the Food service apply the V1.1 1..5 rule and
    return INVALID_IMAGE_COUNT for both a missing field and empty multipart.
    """
    content_type = request.headers.get("content-type", "")
    body = await request.body()
    if _is_empty_multipart_body(content_type, body):
        return [], DEFAULT_CONF_THRESHOLD

    form = await request.form()
    images = [
        value
        for value in form.getlist("images")
        if isinstance(value, StarletteUploadFile)
    ]
    return images, _parse_conf_threshold(form.get("conf_threshold"))


@router.post(
    "/recognitions",
    response_model=ApiResponse,
    status_code=201,
    responses=FOOD_ERROR_RESPONSES,
    openapi_extra=FOOD_UPLOAD_OPENAPI,
)
async def create_food_recognition(
    request: Request,
    current_user: User = Depends(get_current_user),
    service: FoodRecognitionService = Depends(get_food_recognition_service),
):
    images, conf_threshold = await _read_food_upload(request)
    recognition = await service.create_recognition(
        user_id=current_user.id,
        images=images,
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
