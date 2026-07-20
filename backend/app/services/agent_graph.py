"""Two minimal V1 LangGraph flows with no supervisor, tools, or knowledge base."""

from __future__ import annotations

import json
from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from app.entity.recipe_schemas import ChatLLMResult, RecipeGenerateResult
from app.services.agent_prompts import (
    CHAT_SYSTEM_PROMPT,
    RECIPE_GENERATION_SYSTEM_PROMPT,
    RECIPE_GENERATION_USER_PROMPT,
)
from app.services.llm_gateway import get_llm_gateway


class GenerateRecipeState(TypedDict):
    confirmed_ingredients: list[dict]
    preferences: dict
    raw_recipe: RecipeGenerateResult | None


class ChatRecipeState(TypedDict):
    current_recipe: dict
    message: str
    conversation_summary: str
    recent_messages: list[dict[str, str]]
    llm_output: ChatLLMResult | None
    response: dict


async def load_confirmed_ingredients(state: GenerateRecipeState) -> dict:
    if not state["confirmed_ingredients"]:
        raise ValueError("confirmed ingredients are empty")
    return {}


async def generate_recipe(state: GenerateRecipeState) -> dict:
    user_prompt = RECIPE_GENERATION_USER_PROMPT.format(
        confirmed_ingredients_json=json.dumps(
            state["confirmed_ingredients"], ensure_ascii=False
        ),
        preferences_json=json.dumps(state["preferences"], ensure_ascii=False),
    )
    recipe = await get_llm_gateway().generate_recipe(
        RECIPE_GENERATION_SYSTEM_PROMPT,
        user_prompt,
        state["confirmed_ingredients"],
        state["preferences"],
    )
    return {"raw_recipe": recipe}


async def validate_and_save(state: GenerateRecipeState) -> dict:
    return {"raw_recipe": RecipeGenerateResult.model_validate(state["raw_recipe"])}


async def load_recipe_context(state: ChatRecipeState) -> dict:
    if not state["current_recipe"]:
        raise ValueError("recipe context is empty")
    return {}


async def call_llm(state: ChatRecipeState) -> dict:
    prompt = (
        f"当前菜谱：\n{json.dumps(state['current_recipe'], ensure_ascii=False)}"
        f"\n\n较早对话摘要：\n{state.get('conversation_summary') or '无'}"
        "\n\n最近对话：\n"
        f"{json.dumps(state.get('recent_messages') or [], ensure_ascii=False)}"
        f"\n\n用户消息：\n{state['message']}"
    )
    output = await get_llm_gateway().chat(
        CHAT_SYSTEM_PROMPT, prompt, state["current_recipe"]
    )
    return {"llm_output": output}


def route_by_action(state: ChatRecipeState) -> str:
    output = state["llm_output"]
    if output is None:
        raise ValueError("missing chat LLM output")
    return output.action


async def answer(state: ChatRecipeState) -> dict:
    return {"response": state["llm_output"].model_dump(mode="json")}


async def update_recipe(state: ChatRecipeState) -> dict:
    return {"response": state["llm_output"].model_dump(mode="json")}


def build_generate_recipe_graph():
    graph = StateGraph(GenerateRecipeState)
    graph.add_node("load_confirmed_ingredients", load_confirmed_ingredients)
    graph.add_node("generate_recipe", generate_recipe)
    graph.add_node("validate_and_save", validate_and_save)
    graph.add_edge(START, "load_confirmed_ingredients")
    graph.add_edge("load_confirmed_ingredients", "generate_recipe")
    graph.add_edge("generate_recipe", "validate_and_save")
    graph.add_edge("validate_and_save", END)
    return graph.compile()


def build_chat_recipe_graph():
    graph = StateGraph(ChatRecipeState)
    graph.add_node("load_recipe_context", load_recipe_context)
    graph.add_node("call_llm", call_llm)
    graph.add_node("answer", answer)
    graph.add_node("update_recipe", update_recipe)
    graph.add_edge(START, "load_recipe_context")
    graph.add_edge("load_recipe_context", "call_llm")
    graph.add_conditional_edges(
        "call_llm",
        route_by_action,
        {"answer": "answer", "update_recipe": "update_recipe"},
    )
    graph.add_edge("answer", END)
    graph.add_edge("update_recipe", END)
    return graph.compile()


generate_recipe_graph = build_generate_recipe_graph()
chat_recipe_graph = build_chat_recipe_graph()
