"""
对话服务模块
修改人：陈煜君
新增V1 菜谱对话，旧版对话保留
"""
import asyncio
import json
import time
import uuid
from typing import AsyncGenerator, Dict, List, Optional, Any

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
        """获取 Agent 图实例（旧版，保留兼容）"""
        if self.agent_graph is None:
            from app.services.agent_graph import get_agent_graph
            self.agent_graph = get_agent_graph()
        return self.agent_graph

    # ============================================================
    # 会话管理（V1 第八节第1点）
    # ============================================================

    def create_session(
        self,
        db: Session,
        user_id: int,
        recipe_id: Optional[int] = None,
        title: Optional[str] = None,
    ) -> ChatSession:
        """
        创建对话会话（V1 第八节第1点）

        Args:
            db: 数据库会话
            user_id: 用户ID
            recipe_id: 关联的菜谱 ID（可选）
            title: 会话标题

        Returns:
            创建的会话
        """
        session_title = title or f"菜谱对话 #{recipe_id}" if recipe_id else "新对话"
        session = ChatSession(
            user_id=user_id,
            session_uuid=str(uuid.uuid4()),
            title=session_title,
            recipe_id=recipe_id,  # V1 增加 recipe_id 字段
            status="active",
            message_count=0,
            last_message_at=now_cst(),
        )
        db.add(session)
        db.commit()
        db.refresh(session)

        logger.info(f"创建对话会话: session_id={session.id}, user_id={user_id}, recipe_id={recipe_id}")
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
        """构建发送给 Agent 的消息列表"""
        messages = []
        for msg in history:
            if msg["role"] == "user":
                messages.append(HumanMessage(content=msg["content"]))
            elif msg["role"] == "assistant":
                messages.append(AIMessage(content=msg["content"]))
        messages.append(HumanMessage(content=new_message))
        return messages

    # ============================================================
    # 流式对话（旧版，保留兼容）
    # ============================================================

    async def send_message_stream(
        self, db: Session, session_id: int, message: str
    ) -> AsyncGenerator[str, None]:
        """
        发送消息并获取流式响应（旧版，保留兼容）
        """
        from app.database.session import SessionLocal

        own_db = SessionLocal()
        start_time = time.time()

        try:
            history = self.get_history(own_db, session_id, limit=20)
            self.save_message(own_db, session_id, "user", message)
            messages = self._build_messages_for_agent(history, message)

            full_response = ""
            agent_used = None

            try:
                graph = self._get_agent_graph()
                initial_state = {
                    "messages": messages,
                    "next_agent": "",
                    "detection_results": None,
                    "analysis_report": None,
                    "current_task": None,
                }

                async for event in graph.astream_events(
                    initial_state,
                    config={"recursion_limit": 10},
                    version="v2",
                ):
                    event_kind = event["event"]

                    if event_kind == "on_chat_model_stream":
                        chunk = event["data"]["chunk"]
                        if hasattr(chunk, "content") and chunk.content:
                            token = chunk.content
                            full_response += token
                            yield f"data: {json.dumps({'type': 'token', 'content': token})}\n\n"

                    elif event_kind == "on_tool_start":
                        tool_name = event.get("name", "unknown")
                        tool_input = event["data"].get("input", {})
                        yield f"data: {json.dumps({'type': 'tool_call', 'tool': tool_name, 'input': str(tool_input)})}\n\n"

                    elif event_kind == "on_tool_end":
                        tool_output = event["data"].get("output", "")
                        yield f"data: {json.dumps({'type': 'tool_result', 'output': str(tool_output)[:500]})}\n\n"

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

                latency_ms = int((time.time() - start_time) * 1000)

                if full_response:
                    self.save_message(
                        own_db,
                        session_id,
                        "assistant",
                        full_response,
                        agent_used=agent_used,
                        latency_ms=latency_ms,
                    )

                yield f"data: {json.dumps({'type': 'done', 'latency_ms': latency_ms})}\n\n"

            except Exception as e:
                logger.error(f"Agent 执行失败: {e}")
                error_msg = f"抱歉，处理您的请求时出现错误: {str(e)}"
                self.save_message(own_db, session_id, "assistant", error_msg)
                yield f"data: {json.dumps({'type': 'error', 'content': error_msg})}\n\n"

        finally:
            own_db.close()

    # ============================================================
    # 菜谱对话流式响应（V1 第八节）- 新增
    # ============================================================

    async def send_recipe_chat_stream(
        self,
        recipe_id: int,
        user_id: int,
        message: str,
    ) -> AsyncGenerator[str, None]:
        """
        菜谱对话流式响应（V1 第八节）

        只发送四种 SSE 事件：
        - token: 回答内容
        - recipe_updated: 菜谱更新（version + 1）
        - done: 完成
        - error: 错误

        Args:
            recipe_id: 菜谱 ID
            user_id: 用户 ID
            message: 用户消息

        Yields:
            SSE 格式消息
        """
        import time
        start_time = time.time()

        try:
            from app.services.agent_graph import chat_recipe_graph
            from app.services.recipe_service import recipe_service

            # 1. 获取当前菜谱（验证权限）
            recipe = await recipe_service.get_recipe(recipe_id, user_id)

            # 2. 调用 Agent Graph（V1 第八节第3点）
            result = await chat_recipe_graph.ainvoke({
                "recipe_id": recipe_id,
                "user_id": user_id,
                "message": message,
                "current_recipe": recipe.model_dump(),
                "llm_output": {},
                "response": {},
            })

            response = result.get("response", {})
            action = response.get("action", "answer")

            # 3. 流式输出回答（token 事件）
            answer_text = response.get("answer", "")
            if answer_text:
                # 模拟逐字流式输出
                for char in answer_text:
                    yield f"event: token\ndata: {json.dumps({'content': char})}\n\n"
                    await asyncio.sleep(0.02)

            # 4. 如果需要更新菜谱（recipe_updated 事件）
            if action == "update_recipe":
                updated_data = response.get("recipe", {})
                if updated_data:
                    updated_recipe = await recipe_service.update_recipe(
                        recipe_id=recipe_id,
                        user_id=user_id,
                        new_recipe_data=updated_data,
                    )
                    yield f"event: recipe_updated\ndata: {json.dumps({'recipe_id': recipe_id, 'version': updated_recipe.version})}\n\n"
                    logger.info(f"菜谱已更新: recipe_id={recipe_id}, version={updated_recipe.version}")

            # 5. 完成事件
            latency_ms = int((time.time() - start_time) * 1000)
            yield f"event: done\ndata: {json.dumps({'message_id': 0, 'latency_ms': latency_ms})}\n\n"

        except Exception as e:
            logger.error(f"菜谱对话失败: {e}", exc_info=True)
            yield f"event: error\ndata: {json.dumps({'code': 'LLM_UNAVAILABLE', 'message': str(e)})}\n\n"
            # 即使失败也要发送 done
            yield "event: done\ndata: {}\n\n"

    # ============================================================
    # 会话列表与删除（保持兼容）
    # ============================================================

    def get_session_list(
        self, db: Session, user_id: int, page: int = 1, page_size: int = 20
    ) -> Dict[str, Any]:
        """获取会话列表"""
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
                    "recipe_id": s.recipe_id,  # V1 增加
                    "message_count": s.message_count,
                    "last_message_at": s.last_message_at.isoformat() if s.last_message_at else None,
                    "created_at": s.created_at.isoformat() if s.created_at else None,
                }
                for s in sessions
            ],
        }

    def delete_session(self, db: Session, session_id: int, user_id: int) -> bool:
        """删除会话（软删除）"""
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