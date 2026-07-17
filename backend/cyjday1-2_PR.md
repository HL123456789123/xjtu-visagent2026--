# 陈煜君 Day 1 -2PR

**日期**：2026-07-14 -15 

---

**标题**：`feat(recipe): 菜谱模块 V1 规范重构 (Day1修正 + Day2)`

**描述**：

#### 本次 PR 内容

| 类型    | 文件                     | 说明                                           |
| :------ | :----------------------- | :--------------------------------------------- |
| Schema  | `recipe_schemas.py`      | 完全按 V1 规范重写                             |
| Service | `recipe_service.py`      | V1 执行版，LLM 调用 + 降级                     |
| Prompt  | `agent_prompts.py`       | 新增 V1 固定 Prompt                            |
| Graph   | `agent_graph.py`         | 两条最小 LangGraph 流程                        |
| SSE     | `chat_service.py`        | 四类事件：token/recipe_updated/done/error      |
| API     | `api/recipes.py`         | 适配 V1 规范                                   |
| API     | `api/chat.py`            | 独立 Chat API                                  |
| Test    | `test_recipe_schemas.py` | 适配新 Schema                                  |
| Core    | app/core/exceptions.py   | 新增菜谱生成失败、菜谱不存在异常和权限不足异常 |

#### V1 规范对齐检查

- 第六节 Recipe API（POST /api/recipes + GET /api/recipes/{id}）
- 第七节 LLM 输入输出（固定 Prompt + RecipeGenerateResult）
- 第八节 Chat API（session + SSE 四类事件）
- 第九节 Repository 接口（预留调用位置）

#### 测试情况

- Schema Pydantic 校验测试通过
- 数据库测试（需要启动 PostgreSQL，所以没有完成）
- 端到端测试（等待 Day3 集成）

#### 待完成（Day3）

- 对接 FoodRepository（绕家辉）
- 对接 RecipeRepository（绕家辉）
- 对接 ChatRepository（绕家辉）
- 真实 LLM 接入（Day4）

## 🔄 回滚方案

如果 CI 检查失败，可以直接 revert：

bash

```
git revert HEAD
git push origin feature/backend-recipe-service
```

