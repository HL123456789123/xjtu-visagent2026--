"""
LangGraph Agent 模块
实现多 Agent 协作的对话系统
包括 Supervisor 路由、检测 Agent、分析 Agent、问答 Agent
"""

from typing import TypedDict, Annotated, Optional
import threading

import httpx
from langchain_core.messages import AIMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import create_react_agent

from app.config.settings import settings
from app.core.logger import get_logger
from app.services.agent_tools import get_all_tools
from app.services.agent_prompts import (
    SUPERVISOR_SYSTEM_PROMPT,
    DETECTION_SYSTEM_PROMPT,
    ANALYSIS_SYSTEM_PROMPT,
    QA_SYSTEM_PROMPT,
)

logger = get_logger("agent_graph")


# ── 状态定义 ──────────────────────────────────────────


class AgentState(TypedDict):
    """Agent 状态"""

    messages: Annotated[list, "对话消息列表"]
    next_agent: Annotated[str, "下一个处理的 Agent"]
    detection_results: Annotated[Optional[dict], "检测结果"]
    analysis_report: Annotated[Optional[str], "分析报告"]
    current_task: Annotated[Optional[str], "当前任务类型"]


# ── LLM 初始化 ────────────────────────────────────────

# LLM 实例缓存，避免每次调用都创建新实例
_llm_cache = None
_llm_lock = threading.Lock()


def get_llm():
    """获取 LLM 实例（缓存复用，线程安全）"""
    global _llm_cache
    if _llm_cache is not None:
        return _llm_cache

    with _llm_lock:
        if _llm_cache is not None:
            return _llm_cache

        # 创建自定义 httpx 客户端，禁用 HTTP/2 并增加超时
        http_async_client = httpx.AsyncClient(http2=False, timeout=60.0, follow_redirects=True)

        _llm_cache = ChatOpenAI(
            model=settings.OPENAI_MODEL,
            openai_api_key=settings.OPENAI_API_KEY,
            openai_api_base=settings.OPENAI_BASE_URL,
            temperature=0.7,
            streaming=True,
            http_async_client=http_async_client,
        )
    return _llm_cache


# ── Supervisor 节点 ───────────────────────────────────


async def supervisor_node(state: AgentState) -> dict:
    """
    Supervisor 路由节点
    使用 LLM 判断用户意图，决定下一步由哪个 Agent 处理
    """
    try:
        llm = get_llm()

        # 构建消息
        messages = [SystemMessage(content=SUPERVISOR_SYSTEM_PROMPT), *state["messages"]]

        # 调用 LLM
        response = await llm.ainvoke(messages)
        content = response.content.strip().lower()

        # 解析 Agent 名称
        if "detection" in content:
            next_agent = "detection_agent"
        elif "analysis" in content:
            next_agent = "analysis_agent"
        elif "qa" in content or "问答" in content:
            next_agent = "qa_agent"
        elif "end" in content or "结束" in content:
            next_agent = "end"
        else:
            # 默认使用问答 Agent
            next_agent = "qa_agent"

        logger.info(f"Supervisor 路由: {next_agent}")

        return {"next_agent": next_agent, "current_task": next_agent}

    except Exception as e:
        logger.error(f"Supervisor 节点执行失败: {type(e).__name__}: {e}")
        return {"next_agent": "qa_agent", "current_task": "qa_agent"}


# ── 检测 Agent 节点 ──────────────────────────────────


async def detection_agent_node(state: AgentState) -> dict:
    """
    检测 Agent 节点
    使用 ReAct Agent 执行检测任务
    """
    try:
        llm = get_llm()
        tools = get_all_tools()

        # 创建 ReAct Agent
        agent = create_react_agent(llm, tools)

        # 构建消息
        messages = [SystemMessage(content=DETECTION_SYSTEM_PROMPT), *state["messages"]]

        # 执行 Agent
        result = await agent.ainvoke({"messages": messages})

        # 提取最后的 AI 消息
        ai_messages = [m for m in result["messages"] if isinstance(m, AIMessage)]
        if ai_messages:
            response_content = ai_messages[-1].content
        else:
            response_content = "检测完成，但未能生成响应。"

        return {
            "messages": [AIMessage(content=response_content)],
            "detection_results": result.get("detection_results"),
        }

    except Exception as e:
        logger.error(f"检测 Agent 执行失败: {e}")
        return {"messages": [AIMessage(content=f"检测过程中出现错误: {str(e)}")]}


# ── 分析 Agent 节点 ──────────────────────────────────


async def analysis_agent_node(state: AgentState) -> dict:
    """
    分析 Agent 节点
    分析检测结果并生成报告
    """
    try:
        llm = get_llm()
        tools = get_all_tools()

        # 创建 ReAct Agent
        agent = create_react_agent(llm, tools)

        # 构建消息
        messages = [SystemMessage(content=ANALYSIS_SYSTEM_PROMPT), *state["messages"]]

        # 执行 Agent
        result = await agent.ainvoke({"messages": messages})

        # 提取最后的 AI 消息
        ai_messages = [m for m in result["messages"] if isinstance(m, AIMessage)]
        if ai_messages:
            response_content = ai_messages[-1].content
        else:
            response_content = "分析完成，但未能生成报告。"

        return {
            "messages": [AIMessage(content=response_content)],
            "analysis_report": response_content,
        }

    except Exception as e:
        logger.error(f"分析 Agent 执行失败: {e}")
        return {"messages": [AIMessage(content=f"分析过程中出现错误: {str(e)}")]}


# ── 问答 Agent 节点 ──────────────────────────────────


async def qa_agent_node(state: AgentState) -> dict:
    """
    问答 Agent 节点
    回答用户问题
    """
    try:
        llm = get_llm()
        tools = get_all_tools()

        # 创建 ReAct Agent
        agent = create_react_agent(llm, tools)

        # 构建消息
        messages = [SystemMessage(content=QA_SYSTEM_PROMPT), *state["messages"]]

        # 执行 Agent
        result = await agent.ainvoke({"messages": messages})

        # 提取最后的 AI 消息
        ai_messages = [m for m in result["messages"] if isinstance(m, AIMessage)]
        if ai_messages:
            response_content = ai_messages[-1].content
        else:
            response_content = "抱歉，我无法回答这个问题。"

        return {"messages": [AIMessage(content=response_content)]}

    except Exception as e:
        logger.error(f"问答 Agent 执行失败: {type(e).__name__}: {e}")
        return {"messages": [AIMessage(content=f"回答问题时出现错误: {str(e)}")]}


# ── 路由函数 ──────────────────────────────────────────


def route_to_agent(state: AgentState) -> str:
    """根据状态决定下一个节点"""
    next_agent = state.get("next_agent", "end")

    if next_agent == "detection_agent":
        return "detection_agent"
    elif next_agent == "analysis_agent":
        return "analysis_agent"
    elif next_agent == "qa_agent":
        return "qa_agent"
    else:
        return "end"


# ── 构建 Agent 图 ─────────────────────────────────────


def build_agent_graph():
    """
    构建 Agent 图

    Returns:
        编译后的 Agent 图
    """
    # 创建状态图
    graph = StateGraph(AgentState)

    # 添加节点
    graph.add_node("supervisor", supervisor_node)
    graph.add_node("detection_agent", detection_agent_node)
    graph.add_node("analysis_agent", analysis_agent_node)
    graph.add_node("qa_agent", qa_agent_node)

    # 添加边
    graph.add_conditional_edges(
        "supervisor",
        route_to_agent,
        {
            "detection_agent": "detection_agent",
            "analysis_agent": "analysis_agent",
            "qa_agent": "qa_agent",
            "end": END,
        },
    )

    # 各 Agent 完成后回到 Supervisor 或结束
    graph.add_edge("detection_agent", "supervisor")
    graph.add_edge("analysis_agent", "supervisor")
    graph.add_edge("qa_agent", END)

    # 设置入口
    graph.set_entry_point("supervisor")

    # 编译图
    compiled_graph = graph.compile()

    logger.info("Agent 图构建完成")
    return compiled_graph


# 全局 Agent 图实例
agent_graph = None


def get_agent_graph():
    """获取全局 Agent 图实例"""
    global agent_graph
    if agent_graph is None:
        agent_graph = build_agent_graph()
    return agent_graph
