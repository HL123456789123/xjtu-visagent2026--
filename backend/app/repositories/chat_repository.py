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

    def list_sessions_for_recipe(self, user_id: int, recipe_id: int) -> list[ChatSession]:
        return (
            self.db.query(ChatSession)
            .filter(
                ChatSession.user_id == user_id,
                ChatSession.recipe_id == recipe_id,
                ChatSession.status == "active",
            )
            .order_by(ChatSession.last_message_at.desc(), ChatSession.created_at.desc())
            .all()
        )

    def get_latest_session_for_recipe(self, user_id: int, recipe_id: int) -> ChatSession | None:
        sessions = self.list_sessions_for_recipe(user_id, recipe_id)
        return sessions[0] if sessions else None

    def list_messages_for_session(self, session_id: int) -> list[ChatMessage]:
        return (
            self.db.query(ChatMessage)
            .filter(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.created_at.asc(), ChatMessage.id.asc())
            .all()
        )

    def get_message(self, message_id: int) -> ChatMessage | None:
        return self.db.get(ChatMessage, message_id)

    def save_message(
        self,
        session_id: int,
        role: str,
        content: str,
        *,
        recipe_version: int | None = None,
    ) -> ChatMessage:
        message = ChatMessage(
            session_id=session_id,
            role=role,
            content=content,
            recipe_version=recipe_version,
        )
        session = self.db.get(ChatSession, session_id)
        if session is None:
            raise ValueError("会话不存在")
        session.message_count = (session.message_count or 0) + 1
        session.last_message_at = datetime.now().astimezone()
        self.db.add(message)
        self._commit_and_refresh(message)
        return message

    def attach_recipe_version(self, message_id: int, recipe_version: int) -> None:
        message = self.db.get(ChatMessage, message_id)
        if message is None:
            raise ValueError("消息不存在")
        message.recipe_version = recipe_version
        try:
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

    def get_conversation_context(
        self, session_id: int, *, recent_limit: int = 12
    ) -> tuple[str, list[dict[str, str]]]:
        session = self.db.get(ChatSession, session_id)
        if session is None:
            raise ValueError("会话不存在")
        messages = self.list_messages_for_session(session_id)
        recent = messages[-recent_limit:]
        return session.context_summary or "", [
            {"role": message.role, "content": message.content} for message in recent
        ]

    def refresh_context_summary(self, session_id: int, *, recent_limit: int = 12) -> None:
        session = self.db.get(ChatSession, session_id)
        if session is None:
            raise ValueError("会话不存在")
        messages = self.list_messages_for_session(session_id)
        older = messages[:-recent_limit]
        if not older:
            return
        role_names = {"user": "用户", "assistant": "助手"}
        lines = [
            f"{role_names.get(message.role, message.role)}：{message.content[:240]}"
            for message in older
        ]
        session.context_summary = "\n".join(lines)[-3000:]
        session.summary_through_message_id = older[-1].id
        try:
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

    def _commit_and_refresh(self, entity) -> None:
        try:
            self.db.commit()
            self.db.refresh(entity)
        except Exception:
            self.db.rollback()
            raise
