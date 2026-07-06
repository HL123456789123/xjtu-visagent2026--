"""
对话模块 API 路由
提供对话会话管理、消息发送等接口
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.security import get_current_user, RequirePermission
from app.database.session import get_db
from app.entity.db_models import User, ChatSession
from app.entity.schemas import ApiResponse, SendMessageRequest
from app.services.chat_service import chat_service

router = APIRouter(prefix="/api/chat", tags=["智能对话"])


@router.post("/sessions", response_model=ApiResponse, dependencies=[Depends(RequirePermission("agent:chat"))])
async def create_session(
    title: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """创建对话会话"""
    session = chat_service.create_session(db=db, user_id=current_user.id, title=title)

    return ApiResponse(
        code=200,
        message="会话创建成功",
        data={
            "session_id": session.id,
            "session_uuid": session.session_uuid,
            "title": session.title,
        },
    )


@router.post("/sessions/{session_id}/messages", dependencies=[Depends(RequirePermission("agent:chat"))])
async def send_message(
    session_id: int,
    body: SendMessageRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    发送消息（SSE 流式响应）

    返回 SSE 格式的流式响应：
    - token: AI 回复的 token
    - tool_call: 工具调用
    - tool_result: 工具执行结果
    - done: 完成信号
    - error: 错误信息
    """
    # 验证会话是否存在且属于当前用户

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


@router.get("/sessions/{session_id}/messages", response_model=ApiResponse, dependencies=[Depends(RequirePermission("agent:chat"))])
async def get_messages(
    session_id: int,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取对话历史"""
    # 验证会话是否存在且属于当前用户

    session = (
        db.query(ChatSession)
        .filter(ChatSession.id == session_id, ChatSession.user_id == current_user.id)
        .first()
    )

    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")

    messages = chat_service.get_history(db, session_id, limit=limit)

    return ApiResponse(code=200, data={"session_id": session_id, "messages": messages})


@router.get("/sessions", response_model=ApiResponse, dependencies=[Depends(RequirePermission("agent:chat"))])
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


@router.delete("/sessions/{session_id}", response_model=ApiResponse, dependencies=[Depends(RequirePermission("agent:chat"))])
async def delete_session(
    session_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    """删除会话"""
    success = chat_service.delete_session(db, session_id, current_user.id)

    if not success:
        raise HTTPException(status_code=404, detail="会话不存在")

    return ApiResponse(code=200, message="会话已删除")
