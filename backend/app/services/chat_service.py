"""
对话服务模块
提供对话会话管理和流式响应功能
"""

import uuid
import json
from typing import Dict, List, Optional, Any, AsyncGenerator

from langchain_core.messages import HumanMessage, AIMessage
from sqlalchemy.orm import Session

from app.core.logger import get_logger
from app.core.tz import now_cst
from app.entity.db_models import ChatSession, ChatMessage

logger = get_logger("chat_service")


class ChatService:
    """对话服务类"""

    def __init__(self):
        self.agent_graph = None

    def _get_agent_graph(self):
        """获取 Agent 图实例"""
        if self.agent_graph is None:
            from app.services.agent_graph import get_agent_graph

            self.agent_graph = get_agent_graph()
        return self.agent_graph

    def create_session(self, db: Session, user_id: int, title: Optional[str] = None) -> ChatSession:
        """
        创建对话会话

        Args:
            db: 数据库会话
            user_id: 用户ID
            title: 会话标题

        Returns:
            创建的会话
        """
        session = ChatSession(
            user_id=user_id,
            session_uuid=str(uuid.uuid4()),
            title=title or "新对话",
            status="active",
            message_count=0,
            last_message_at=now_cst(),
        )
        db.add(session)
        db.commit()
        db.refresh(session)

        logger.info(f"创建对话会话: session_id={session.id}, user_id={user_id}")
        return session

    def save_message(
        self,
        db: Session,
        session_id: int,
        role: str,
        content: str,
        agent_used: Optional[str] = None,
        tool_calls: Optional[List[Dict]] = None,
        tool_result: Optional[str] = None,
        tokens_used: Optional[int] = None,
        latency_ms: Optional[int] = None,
    ) -> ChatMessage:
        """
        保存消息到数据库

        Args:
            db: 数据库会话
            session_id: 会话ID
            role: 消息角色
            content: 消息内容
            agent_used: 使用的 Agent
            tool_calls: 工具调用记录
            tool_result: 工具调用结果
            tokens_used: Token 消耗量
            latency_ms: 响应耗时

        Returns:
            保存的消息
        """
        message = ChatMessage(
            session_id=session_id,
            role=role,
            content=content,
            agent_used=agent_used,
            tool_calls=tool_calls,
            tool_result=tool_result,
            tokens_used=tokens_used,
            latency_ms=latency_ms,
        )
        db.add(message)

        # 更新会话信息
        session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
        if session:
            session.message_count += 1
            session.last_message_at = now_cst()

        db.commit()
        db.refresh(message)
        return message

    def get_history(self, db: Session, session_id: int, limit: int = 50) -> List[Dict[str, Any]]:
        """
        获取对话历史

        Args:
            db: 数据库会话
            session_id: 会话ID
            limit: 返回消息数量限制

        Returns:
            消息列表
        """
        messages = (
            db.query(ChatMessage)
            .filter(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.created_at.asc(), ChatMessage.id.asc())
            .limit(limit)
            .all()
        )

        return [
            {
                "id": m.id,
                "role": m.role,
                "content": m.content,
                "agent_used": m.agent_used,
                "tool_calls": m.tool_calls,
                "created_at": m.created_at.isoformat() if m.created_at else None,
            }
            for m in messages
        ]

    def _build_messages_for_agent(self, history: List[Dict[str, Any]], new_message: str) -> List:
        """
        构建发送给 Agent 的消息列表

        Args:
            history: 历史消息
            new_message: 新消息

        Returns:
            LangChain 消息列表
        """
        messages = []

        for msg in history:
            if msg["role"] == "user":
                messages.append(HumanMessage(content=msg["content"]))
            elif msg["role"] == "assistant":
                messages.append(AIMessage(content=msg["content"]))

        messages.append(HumanMessage(content=new_message))
        return messages

    async def send_message_stream(
        self, db: Session, session_id: int, message: str
    ) -> AsyncGenerator[str, None]:
        """
        发送消息并获取流式响应

        Args:
            db: 数据库会话
            session_id: 会话ID
            message: 用户消息

        Yields:
            SSE 格式的消息
        """
        import time

        start_time = time.time()

        # 先获取历史消息（不含当前用户消息），再保存用户消息，避免“先存后取再剔除”的冗余逻辑
        history = self.get_history(db, session_id, limit=20)

        # 保存用户消息
        self.save_message(db, session_id, "user", message)

        # 构建消息列表：history（旧历史）+ 当前新消息
        messages = self._build_messages_for_agent(history, message)

        # 流式执行 Agent
        full_response = ""
        agent_used = None

        try:
            # 获取 Agent 图
            graph = self._get_agent_graph()

            # 初始化状态
            initial_state = {
                "messages": messages,
                "next_agent": "",
                "detection_results": None,
                "analysis_report": None,
                "current_task": None,
            }

            # 流式执行（设置递归限制防止无限循环）
            async for event in graph.astream_events(
                initial_state,
                config={"recursion_limit": 10},
                version="v2",
            ):
                event_kind = event["event"]

                # 处理 LLM 流式输出
                if event_kind == "on_chat_model_stream":
                    chunk = event["data"]["chunk"]
                    if hasattr(chunk, "content") and chunk.content:
                        token = chunk.content
                        full_response += token
                        yield f"data: {json.dumps({'type': 'token', 'content': token})}\n\n"

                # 处理工具调用
                elif event_kind == "on_tool_start":
                    tool_name = event.get("name", "unknown")
                    tool_input = event["data"].get("input", {})
                    yield f"data: {json.dumps({'type': 'tool_call', 'tool': tool_name, 'input': str(tool_input)})}\n\n"

                # 处理工具结果
                elif event_kind == "on_tool_end":
                    tool_output = event["data"].get("output", "")
                    yield f"data: {json.dumps({'type': 'tool_result', 'output': str(tool_output)[:500]})}\n\n"

                # 处理节点执行
                elif event_kind == "on_chain_start":
                    node_name = event.get("name", "")
                    if "supervisor" in node_name:
                        agent_used = "supervisor"
                    elif "detection" in node_name:
                        agent_used = "detection_agent"
                    elif "analysis" in node_name:
                        agent_used = "analysis_agent"
                    elif "qa" in node_name:
                        agent_used = "qa_agent"

            # 计算耗时
            latency_ms = int((time.time() - start_time) * 1000)

            # 保存 AI 回复
            if full_response:
                self.save_message(
                    db,
                    session_id,
                    "assistant",
                    full_response,
                    agent_used=agent_used,
                    latency_ms=latency_ms,
                )

            # 发送完成信号
            yield f"data: {json.dumps({'type': 'done', 'latency_ms': latency_ms})}\n\n"

        except Exception as e:
            logger.error(f"Agent 执行失败: {e}")
            error_msg = f"抱歉，处理您的请求时出现错误: {str(e)}"

            # 保存错误消息
            self.save_message(db, session_id, "assistant", error_msg)

            yield f"data: {json.dumps({'type': 'error', 'content': error_msg})}\n\n"

    def get_session_list(
        self, db: Session, user_id: int, page: int = 1, page_size: int = 20
    ) -> Dict[str, Any]:
        """
        获取会话列表

        Args:
            db: 数据库会话
            user_id: 用户ID
            page: 页码
            page_size: 每页数量

        Returns:
            分页结果
        """
        query = db.query(ChatSession).filter(
            ChatSession.user_id == user_id, ChatSession.status == "active"
        )

        total = query.count()
        sessions = (
            query.order_by(ChatSession.last_message_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )

        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "items": [
                {
                    "id": s.id,
                    "session_uuid": s.session_uuid,
                    "title": s.title,
                    "message_count": s.message_count,
                    "last_message_at": s.last_message_at.isoformat() if s.last_message_at else None,
                    "created_at": s.created_at.isoformat() if s.created_at else None,
                }
                for s in sessions
            ],
        }

    def delete_session(self, db: Session, session_id: int, user_id: int) -> bool:
        """
        删除会话（软删除）

        Args:
            db: 数据库会话
            session_id: 会话ID
            user_id: 用户ID

        Returns:
            是否成功删除
        """
        session = (
            db.query(ChatSession)
            .filter(ChatSession.id == session_id, ChatSession.user_id == user_id)
            .first()
        )

        if not session:
            return False

        session.status = "archived"
        db.commit()

        logger.info(f"删除会话: session_id={session_id}")
        return True


# 全局对话服务实例
chat_service = ChatService()
