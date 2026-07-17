"""Chat 数据访问层。"""

import uuid

from sqlalchemy.orm import Session

from app.core.tz import now_cst
from app.entity.db_models import ChatMessage, ChatSession


class ChatRepository:
    def create_session(self, db: Session, user_id: int, recipe_id: int) -> ChatSession:
        session = ChatSession(
            user_id=user_id,
            recipe_id=recipe_id,
            session_uuid=str(uuid.uuid4()),
            title=f"菜谱对话 #{recipe_id}",
            status="active",
            message_count=0,
            last_message_at=now_cst(),
        )
        db.add(session)
        db.commit()
        db.refresh(session)
        return session

    def get_session_for_user(self, db: Session, session_id: int, user_id: int):
        return db.query(ChatSession).filter(
            ChatSession.id == session_id,
            ChatSession.user_id == user_id,
            ChatSession.status == "active",
        ).first()

    def save_message(self, db: Session, session_id: int, role: str, content: str) -> ChatMessage:
        message = ChatMessage(session_id=session_id, role=role, content=content)
        db.add(message)
        session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
        if session:
            session.message_count = (session.message_count or 0) + 1
            session.last_message_at = now_cst()
        db.commit()
        db.refresh(message)
        return message


chat_repository = ChatRepository()
