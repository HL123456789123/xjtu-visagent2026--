"""
Recipe Service 单元测试（Day 2）
不依赖数据库和真实 LLM，只测试内存逻辑
"""
import pytest
from app.services.recipe_service import recipe_service
from app.entity.recipe_schema import RecipeCreateRequest, RecipePreferences
from app.core.exceptions import RecipeNotFoundError, PermissionDeniedError


@pytest.mark.asyncio
async def test_create_recipe_success():
    """测试：正常生成菜谱"""
    request = RecipeCreateRequest(
        recognition_id=1,
        preferences=RecipePreferences(servings=2, taste="清淡")
    )
    result = await recipe_service.create_recipe(request, user_id=1)
    
    assert result.recipe_id == 1
    assert result.version == 1
    assert result.title == "番茄炒蛋"  # Mock 固定返回


@pytest.mark.asyncio
async def test_get_recipe_success():
    """测试：成功查询菜谱"""
    # 先创建一个
    request = RecipeCreateRequest(recognition_id=1)
    created = await recipe_service.create_recipe(request, user_id=1)
    
    # 再查询
    result = await recipe_service.get_recipe(created.recipe_id, user_id=1)
    assert result.recipe_id == created.recipe_id


@pytest.mark.asyncio
async def test_get_recipe_not_found():
    """测试：菜谱不存在 -> 抛 RecipeNotFoundError"""
    with pytest.raises(RecipeNotFoundError):
        await recipe_service.get_recipe(recipe_id=999, user_id=1)


@pytest.mark.asyncio
async def test_get_recipe_permission_denied():
    """测试：访问他人菜谱 -> 抛 PermissionDeniedError"""
    # 用户 1 创建
    request = RecipeCreateRequest(recognition_id=1)
    created = await recipe_service.create_recipe(request, user_id=1)
    
    # 用户 2 查询 -> 403
    with pytest.raises(PermissionDeniedError):
        await recipe_service.get_recipe(created.recipe_id, user_id=2)

# ============================================================
# 异常场景测试：422 / 503（V1 第十一节）
# ============================================================

@pytest.mark.asyncio
async def test_create_recipe_no_confirmed_ingredients():
    """
    测试：未确认食材 -> 抛出 RecipeGenerationError (422)
    
    注意：由于当前 agent_graph 是硬编码 Mock，不会抛出"未确认食材"异常。
    这个测试暂时跳过，Day3 对接 Repository 后启用。
    """
    pytest.skip("Day3 对接 Repository 后启用")


@pytest.mark.asyncio
async def test_create_recipe_invalid_llm_output():
    """
    测试：非法 LLM 输出 -> 抛出 RecipeGenerationError (422)
    
    注意：当前 agent_graph 返回固定 Mock 数据，不会产生非法输出。
    这个测试暂时跳过，Day4 对接真实 LLM 后启用。
    """
    pytest.skip("Day4 对接真实 LLM 后启用")


@pytest.mark.asyncio
async def test_create_recipe_llm_unavailable():
    """
    测试：LLM 不可用 -> 抛出 RecipeGenerationError (503)
    
    注意：当前 Service 使用 Mock，不会触发 LLM 不可用。
    这个测试暂时跳过，Day4 对接真实 LLM 后启用。
    """
    pytest.skip("Day4 对接真实 LLM 后启用")