"""Chat Session 与 Message 的 V1 数据访问实现。"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy.orm import Session

from app.entity.db_models import ChatMessage, ChatSession


class ChatRepository:
    """供 Chat Service 使用的固定 Repository 方法。"""

    def __init__(self, db: Session):
        self.db = db

    def create_session(self, user_id: int, recipe_id: int) -> ChatSession:
        now = datetime.now().astimezone()
        session = ChatSession(
            user_id=user_id,
            recipe_id=recipe_id,
            session_uuid=str(uuid.uuid4()),
            title="新对话",
            status="active",
            message_count=0,
            last_message_at=now,
        )
        self.db.add(session)
        self._commit_and_refresh(session)
        return session

    def get_session_for_user(self, session_id: int, user_id: int) -> ChatSession | None:
        return (
            self.db.query(ChatSession)
            .filter(ChatSession.id == session_id, ChatSession.user_id == user_id)
            .first()
        )

    def get_session(self, session_id: int) -> ChatSession | None:
        """Internal ownership check helper; callers do not write SQLAlchemy queries."""
        return self.db.get(ChatSession, session_id)

    def save_message(self, session_id: int, role: str, content: str) -> ChatMessage:
        message = ChatMessage(session_id=session_id, role=role, content=content)
        session = self.db.get(ChatSession, session_id)
        if session is None:
            raise ValueError("会话不存在")
        session.message_count = (session.message_count or 0) + 1
        session.last_message_at = datetime.now().astimezone()
        self.db.add(message)
        self._commit_and_refresh(message)
        return message

    def _commit_and_refresh(self, entity) -> None:
        try:
            self.db.commit()
            self.db.refresh(entity)
        except Exception:
            self.db.rollback()
            raise
