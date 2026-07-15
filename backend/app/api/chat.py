"""
对话模块 API 路由（V1 冻结版本）
负责人：陈煜君

V1 第八节：
- POST /api/chat/sessions - 创建会话
- POST /api/chat/sessions/{session_id}/messages - 发送消息（SSE）
- GET /api/chat/sessions - 会话列表
- GET /api/chat/sessions/{session_id}/messages - 历史消息
- DELETE /api/chat/sessions/{session_id} - 删除会话
- POST /api/chat/recipes/{recipe_id}/messages - 菜谱快捷对话（新增）
"""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.security import get_current_user, RequirePermission
from app.database.session import get_db
from app.entity.db_models import User, ChatSession
from app.entity.schemas import ApiResponse, SendMessageRequest, CreateSessionRequest
from app.services.chat_service import chat_service
from app.core.logger import get_logger

logger = get_logger("chat_api")  # 建议补充

router = APIRouter(prefix="/api/chat", tags=["智能对话"])


@router.post(
    "/sessions",
    response_model=ApiResponse,
    dependencies=[Depends(RequirePermission("agent:chat"))],
)
async def create_session(
    body: CreateSessionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """创建对话会话（V1 第八节第1点）"""
    session = chat_service.create_session(
        db=db,
        user_id=current_user.id,
        recipe_id=body.recipe_id,  # V1 支持绑定菜谱
        title=body.title,
    )

    return ApiResponse(
        code=201,  # V1 规范：创建成功返回 201
        message="会话创建成功",
        data={
            "session_id": session.id,
            "session_uuid": session.session_uuid,
            "recipe_id": session.recipe_id,
            "title": session.title,
            "created_at": session.created_at.isoformat() if session.created_at else None,
        },
    )


@router.post(
    "/sessions/{session_id}/messages",
    dependencies=[Depends(RequirePermission("agent:chat"))],
)
async def send_message(
    session_id: int,
    body: SendMessageRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    发送消息（SSE 流式响应）（V1 第八节第2点）

    返回 SSE 格式的流式响应：
    - token: AI 回复的 token
    - tool_call: 工具调用
    - tool_result: 工具执行结果
    - done: 完成信号
    - error: 错误信息
    """
    session = (
        db.query(ChatSession)
        .filter(
            ChatSession.id == session_id,
            ChatSession.user_id == current_user.id,
            ChatSession.status == "active",
        )
        .first()
    )

    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")

    return StreamingResponse(
        chat_service.send_message_stream(db, session_id, body.message),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get(
    "/sessions/{session_id}/messages",
    response_model=ApiResponse,
    dependencies=[Depends(RequirePermission("agent:chat"))],
)
async def get_messages(
    session_id: int,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取对话历史"""
    session = (
        db.query(ChatSession)
        .filter(ChatSession.id == session_id, ChatSession.user_id == current_user.id)
        .first()
    )

    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")

    messages = chat_service.get_history(db, session_id, limit=limit)

    return ApiResponse(code=200, data={"session_id": session_id, "messages": messages})


@router.get(
    "/sessions",
    response_model=ApiResponse,
    dependencies=[Depends(RequirePermission("agent:chat"))],
)
async def get_sessions(
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取会话列表"""
    result = chat_service.get_session_list(
        db=db, user_id=current_user.id, page=page, page_size=page_size
    )
    return ApiResponse(code=200, data=result)


@router.delete(
    "/sessions/{session_id}",
    response_model=ApiResponse,
    dependencies=[Depends(RequirePermission("agent:chat"))],
)
async def delete_session(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """删除会话"""
    success = chat_service.delete_session(db, session_id, current_user.id)
    if not success:
        raise HTTPException(status_code=404, detail="会话不存在")
    return ApiResponse(code=200, message="会话已删除")


# ============================================================
# 新增：菜谱快捷对话（V1 第八节扩展）
# ============================================================

@router.post(
    "/recipes/{recipe_id}/messages",
    dependencies=[Depends(RequirePermission("agent:chat"))],
)
async def send_recipe_message(
    recipe_id: int,
    body: SendMessageRequest,
    current_user: User = Depends(get_current_user),
):
    """
    菜谱快捷对话（SSE 流式响应）

    V1 第八节：四类 SSE 事件
    - event: token  → AI 回答内容
    - event: recipe_updated → 菜谱更新（version + 1）
    - event: done → 完成
    - event: error → 错误

    与 /sessions/{session_id}/messages 的区别：
    - 不需要预先创建会话
    - 直接通过 recipe_id 进行对话
    - 修改菜谱时自动保存新版本
    """
    logger.info(
        f"菜谱快捷对话: recipe_id={recipe_id}, user_id={current_user.id}, "
        f"message={body.message[:50]}..."
    )

    return StreamingResponse(
        chat_service.send_recipe_chat_stream(
            recipe_id=recipe_id,
            user_id=current_user.id,
            message=body.message,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )