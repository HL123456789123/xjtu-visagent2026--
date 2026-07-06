"""测试 OpenAI API 连接"""
import asyncio
import httpx
from app.config.settings import settings


async def test_api_connection():
    """测试 API 连接"""
    print(f"API Base URL: {settings.OPENAI_BASE_URL}")
    print(f"API Key: {settings.OPENAI_API_KEY[:10]}...")
    print(f"Model: {settings.OPENAI_MODEL}")
    print()
    
    # 测试1: 检查 API 端点是否可达
    print("测试1: 检查 API 端点...")
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{settings.OPENAI_BASE_URL}/models",
                headers={"Authorization": f"Bearer {settings.OPENAI_API_KEY}"},
                timeout=10.0
            )
            print(f"  状态码: {response.status_code}")
            if response.status_code == 200:
                print("  ✓ API 端点可达且认证成功")
            elif response.status_code == 401:
                print("  ✗ 认证失败: API Key 无效")
            else:
                print(f"  ✗ 意外的状态码: {response.text[:200]}")
    except httpx.ConnectError as e:
        print(f"  ✗ 连接失败: {e}")
        print("  请检查网络连接和 API 地址")
    except httpx.TimeoutException:
        print("  ✗ 连接超时")
        print("  请检查网络连接")
    except Exception as e:
        print(f"  ✗ 错误: {type(e).__name__}: {e}")
    
    print()
    
    # 测试2: 检查模型列表
    print("测试2: 检查可用模型...")
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{settings.OPENAI_BASE_URL}/models",
                headers={"Authorization": f"Bearer {settings.OPENAI_API_KEY}"},
                timeout=10.0
            )
            if response.status_code == 200:
                models = response.json()
                if "data" in models:
                    model_ids = [m["id"] for m in models["data"][:5]]
                    print(f"  部分可用模型: {model_ids}")
                    if settings.OPENAI_MODEL in [m["id"] for m in models["data"]]:
                        print(f"  ✓ 模型 {settings.OPENAI_MODEL} 可用")
                    else:
                        print(f"  ✗ 模型 {settings.OPENAI_MODEL} 不在可用列表中")
    except Exception as e:
        print(f"  ✗ 无法获取模型列表: {e}")


if __name__ == "__main__":
    asyncio.run(test_api_connection())
