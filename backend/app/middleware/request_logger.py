"""
API 请求日志中间件
- 记录每次请求的方法、路径、客户端 IP、User-Agent
- 记录响应状态码、耗时（毫秒）
- 提供 log_operation() 工具函数，用于在关键接口中记录操作审计日志
"""

import time
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from app.core.logger import get_logger

logger = get_logger("request")


def log_operation(
    db,
    user_id: int = None,
    username: str = None,
    module: str = "system",
    action: str = "unknown",
    target_type: str = None,
    target_id: str = None,
    description: str = None,
    ip_address: str = None,
    user_agent: str = None,
    request_method: str = None,
    request_path: str = None,
    status: str = "success",
    error_message: str = None,
):
    """
    记录操作审计日志

    Args:
        db: 数据库会话
        user_id: 操作用户 ID
        username: 用户名
        module: 操作模块（auth/detection/training/agent/system）
        action: 操作类型（create/update/delete/login/export）
        target_type: 操作对象类型（user/task/model/session）
        target_id: 操作对象 ID
        description: 操作描述
        ip_address: 客户端 IP
        user_agent: 客户端 User-Agent
        request_method: HTTP 方法
        request_path: 请求路径
        status: 操作结果（success/failure）
        error_message: 失败时的错误信息
    """
    try:
        from app.entity.db_models import OperationLog

        log_entry = OperationLog(
            user_id=user_id,
            username=username,
            module=module,
            action=action,
            target_type=target_type,
            target_id=str(target_id) if target_id else None,
            description=description,
            ip_address=ip_address,
            user_agent=user_agent[:500] if user_agent else None,
            request_method=request_method,
            request_path=request_path[:500] if request_path else None,
            status=status,
            error_message=error_message,
        )
        db.add(log_entry)
        db.commit()
    except Exception as e:
        logger.warning(f"操作日志写入失败: {e}")
        try:
            db.rollback()
        except Exception:
            pass


class RequestLoggerMiddleware(BaseHTTPMiddleware):
    """API 请求日志中间件"""

    async def dispatch(self, request: Request, call_next) -> Response:
        # 请求开始时间
        start_time = time.time()

        # 获取客户端信息
        client_host = request.client.host if request.client else "unknown"
        user_agent = request.headers.get("user-agent", "unknown")
        method = request.method
        path = request.url.path

        # 记录请求开始
        logger.info(
            f"Request started | "
            f"Method: {method} | "
            f"Path: {path} | "
            f"Client: {client_host} | "
            f"User-Agent: {user_agent}"
        )

        # 处理请求
        try:
            response = await call_next(request)
        except Exception as e:
            # 记录异常
            logger.error(f"Request failed | Method: {method} | Path: {path} | Error: {str(e)}")
            raise

        # 计算耗时
        process_time = (time.time() - start_time) * 1000  # 转换为毫秒

        # 记录请求完成
        logger.info(
            f"Request completed | "
            f"Method: {method} | "
            f"Path: {path} | "
            f"Status: {response.status_code} | "
            f"Duration: {process_time:.2f}ms"
        )

        # 添加响应头
        response.headers["X-Process-Time"] = f"{process_time:.2f}ms"

        return response
