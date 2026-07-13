"""
全局异常处理模块
- 自定义异常类 AppException
- 全局异常处理函数
- 统一错误响应格式
"""

from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from app.config.settings import settings
from app.core.logger import get_logger

logger = get_logger("exceptions")


class AppException(Exception):
    """
    应用自定义异常

    Args:
        code: 错误码（默认 500）
        message: 错误消息
        detail: 详细信息（可选）
    """

    def __init__(self, code: int = 500, message: str = "服务器内部错误", detail: str = None):
        self.code = code
        self.message = message
        self.detail = detail
        super().__init__(message)


async def app_exception_handler(request: Request, exc: AppException):
    """处理自定义异常"""
    logger.error(
        f"AppException: {exc.message} | "
        f"Path: {request.url.path} | "
        f"Method: {request.method} | "
        f"Detail: {exc.detail}"
    )
    return JSONResponse(
        status_code=exc.code,
        content={
            "code": exc.code,
            "message": exc.message,
            "detail": exc.detail,
        },
    )


async def http_exception_handler(request: Request, exc: HTTPException):
    """处理 HTTP 异常"""
    logger.warning(
        f"HTTPException: {exc.status_code} {exc.detail} | "
        f"Path: {request.url.path} | "
        f"Method: {request.method}"
    )
    # 统一 detail 格式：非字符串类型转为字符串，避免返回原始 dict/list 对象
    detail = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "code": exc.status_code,
            "message": exc.detail if isinstance(exc.detail, str) else "请求错误",
            "detail": detail,
        },
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """处理请求验证异常"""
    errors = exc.errors()
    error_messages = []
    for error in errors:
        loc = " -> ".join(str(item) for item in error.get("loc", []))
        msg = error.get("msg", "")
        error_messages.append(f"{loc}: {msg}")

    logger.warning(
        f"ValidationError: {error_messages} | Path: {request.url.path} | Method: {request.method}"
    )
    return JSONResponse(
        status_code=422,
        content={
            "code": 422,
            "message": "请求参数验证失败",
            "detail": error_messages,
        },
    )


async def general_exception_handler(request: Request, exc: Exception):
    """处理未捕获的异常"""
    logger.error(
        f"Unhandled Exception: {type(exc).__name__}: {str(exc)} | "
        f"Path: {request.url.path} | "
        f"Method: {request.method}",
        exc_info=True,
    )
    # 即使在 DEBUG 模式也限制返回的异常信息，仅返回异常类型名，不暴露堆栈和内部细节
    detail = f"{type(exc).__name__}: {str(exc)[:200]}" if settings.DEBUG else None
    return JSONResponse(
        status_code=500,
        content={
            "code": 500,
            "message": "服务器内部错误",
            "detail": detail,
        },
    )
