"""
LangGraph 最小流程（V1 冻结版本）
负责人：陈煜君

首次生成：START -> load_confirmed_ingredients -> generate_recipe -> validate_and_save -> END
对话修改：START -> load_recipe_context -> call_llm -> route_by_action -> answer/update_recipe -> END
"""

from typing import TypedDict, Optional
from datetime import datetime

from langgraph.graph import StateGraph, END

from app.core.logger import get_logger
from app.entity.recipe_schema import (
    RecipeGenerateResult,
    RecipeResponse,
    GeneratorInfo,
)
from app.services.agent_prompts import NUTRITION_DISCLAIMER

logger = get_logger("agent_graph")


# ══════════════════════════════════════════════════════════════
# 状态定义
# ══════════════════════════════════════════════════════════════

class GenerateRecipeState(TypedDict):
    """首次生成菜谱状态"""
    recognition_id: int
    user_id: int
    preferences: dict
    confirmed_ingredients: list
    raw_recipe: dict
    recipe_response: dict


class ChatRecipeState(TypedDict):
    """对话修改菜谱状态"""
    recipe_id: int
    user_id: int
    message: str
    current_recipe: dict
    llm_output: dict
    response: dict


# ══════════════════════════════════════════════════════════════
# Mock 数据（Fake LLM Fixture）
# ══════════════════════════════════════════════════════════════

MOCK_INGREDIENTS = [
    {"name": "番茄", "class_name": "tomato", "quantity": 2, "unit": "个", "source": "model"},
    {"name": "鸡蛋", "class_name": None, "quantity": 3, "unit": "个", "source": "manual"},
]

MOCK_RECIPE_RAW = {
    "title": "番茄炒蛋",
    "summary": "一道适合两人食用的家常快手菜。",
    "servings": 2,
    "cooking_time_minutes": 20,
    "difficulty": "简单",
    "ingredients": [
        {"name": "番茄", "amount": 2, "unit": "个", "note": None},
        {"name": "鸡蛋", "amount": 3, "unit": "个", "note": None},
    ],
    "steps": [
        {"step_no": 1, "description": "番茄洗净切块。", "duration_minutes": 5},
        {"step_no": 2, "description": "鸡蛋打散加少许盐。", "duration_minutes": 2},
        {"step_no": 3, "description": "热锅凉油，倒入蛋液炒熟盛出。", "duration_minutes": 3},
        {"step_no": 4, "description": "锅中加油，放入番茄翻炒出汁。", "duration_minutes": 3},
        {"step_no": 5, "description": "加入炒好的鸡蛋，加盐调味即可。", "duration_minutes": 2},
    ],
    "nutrition": {
        "basis": "per_serving",
        "calories_kcal": 280,
        "protein_g": 16.5,
        "fat_g": 15.2,
        "carbohydrates_g": 18.4,
    },
}

MOCK_GENERATOR = {
    "provider": "fake",
    "model": "fixture-v1",
    "is_mock": True,
}


# ══════════════════════════════════════════════════════════════
# 首次生成流程节点
# ══════════════════════════════════════════════════════════════

async def load_confirmed_ingredients(state: GenerateRecipeState) -> dict:
    """加载确认食材（Mock 实现）"""
    logger.info(f"加载食材: recognition_id={state['recognition_id']}")
    # TODO: Day3 对接 Repository
    return {"confirmed_ingredients": MOCK_INGREDIENTS}


async def generate_recipe(state: GenerateRecipeState) -> dict:
    """调用 LLM 生成菜谱（Mock 实现）"""
    logger.info("生成菜谱（Mock）")
    # TODO: Day4 对接真实 LLM
    return {"raw_recipe": MOCK_RECIPE_RAW}


async def validate_and_save(state: GenerateRecipeState) -> dict:
    """校验并保存菜谱"""
    logger.info("校验并保存菜谱")
    
    # Pydantic 校验
    recipe = RecipeGenerateResult(**state["raw_recipe"])
    
    # 构建响应
    now = datetime.now()
    response = RecipeResponse(
        recipe_id=1,  # Mock ID
        recognition_id=state["recognition_id"],
        version=1,
        title=recipe.title,
        summary=recipe.summary,
        servings=recipe.servings,
        cooking_time_minutes=recipe.cooking_time_minutes,
        difficulty=recipe.difficulty,
        ingredients=recipe.ingredients,
        steps=recipe.steps,
        nutrition=recipe.nutrition,
        nutrition_disclaimer=NUTRITION_DISCLAIMER,
        generator=GeneratorInfo(**MOCK_GENERATOR),
        created_at=now,
        updated_at=now,
    )
    
    return {"recipe_response": response.model_dump()}


# ══════════════════════════════════════════════════════════════
# 对话流程节点
# ══════════════════════════════════════════════════════════════

async def load_recipe_context(state: ChatRecipeState) -> dict:
    """加载菜谱上下文（Mock 实现）"""
    logger.info(f"加载菜谱: recipe_id={state['recipe_id']}")
    # TODO: Day3 对接 Repository
    return {"current_recipe": MOCK_RECIPE_RAW}


async def call_llm(state: ChatRecipeState) -> dict:
    """调用 LLM（Mock 实现）"""
    logger.info(f"调用 LLM: message={state['message']}")
    # TODO: Day4 对接真实 LLM
    
    # Mock: 简单判断是否修改请求
    if "改" in state["message"] or "调整" in state["message"]:
        return {
            "llm_output": {
                "action": "update_recipe",
                "answer": "已经调整为三人份。",
                "recipe": {**MOCK_RECIPE_RAW, "servings": 3},
            }
        }
    else:
        return {
            "llm_output": {
                "action": "answer",
                "answer": "这道番茄炒蛋营养丰富，适合日常食用。",
                "recipe": None,
            }
        }


def route_by_action(state: ChatRecipeState) -> str:
    """根据 action 路由"""
    action = state["llm_output"].get("action", "answer")
    return action


async def answer(state: ChatRecipeState) -> dict:
    """直接回答"""
    logger.info("直接回答")
    return {
        "response": {
            "action": "answer",
            "answer": state["llm_output"]["answer"],
            "message_id": 9001,  # Mock ID
        }
    }


async def update_recipe(state: ChatRecipeState) -> dict:
    """更新菜谱"""
    logger.info("更新菜谱")
    
    # Pydantic 校验
    recipe = RecipeGenerateResult(**state["llm_output"]["recipe"])
    
    return {
        "response": {
            "action": "update_recipe",
            "answer": state["llm_output"]["answer"],
            "recipe_id": state["recipe_id"],
            "version": 2,  # Mock 版本
            "message_id": 9002,  # Mock ID
        }
    }


# ══════════════════════════════════════════════════════════════
# 构建 Graph
# ══════════════════════════════════════════════════════════════

def build_generate_recipe_graph():
    """构建首次生成流程图"""
    graph = StateGraph(GenerateRecipeState)
    
    graph.add_node("load_confirmed_ingredients", load_confirmed_ingredients)
    graph.add_node("generate_recipe", generate_recipe)
    graph.add_node("validate_and_save", validate_and_save)
    
    graph.set_entry_point("load_confirmed_ingredients")
    graph.add_edge("load_confirmed_ingredients", "generate_recipe")
    graph.add_edge("generate_recipe", "validate_and_save")
    graph.add_edge("validate_and_save", END)
    
    return graph.compile()


def build_chat_recipe_graph():
    """构建对话流程图"""
    graph = StateGraph(ChatRecipeState)
    
    graph.add_node("load_recipe_context", load_recipe_context)
    graph.add_node("call_llm", call_llm)
    graph.add_node("answer", answer)
    graph.add_node("update_recipe", update_recipe)
    
    graph.set_entry_point("load_recipe_context")
    graph.add_edge("load_recipe_context", "call_llm")
    graph.add_conditional_edges(
        "call_llm",
        route_by_action,
        {"answer": "answer", "update_recipe": "update_recipe"},
    )
    graph.add_edge("answer", END)
    graph.add_edge("update_recipe", END)
    
    return graph.compile()


# 全局实例
generate_recipe_graph = build_generate_recipe_graph()
chat_recipe_graph = build_chat_recipe_graph()