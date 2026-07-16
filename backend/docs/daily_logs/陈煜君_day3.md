# 陈煜君 Day 3：Mock 全链路

## 今日完成

- 将 Recipe 从内存字典切换为 Repository 接口，持久化结构对应 PostgreSQL 的 `recipes` 表。
- 增加 `FoodRecognitionTask` 读取适配点；目标检测尚未接入时，测试通过固定确认食材写入该表。
- 将 Chat Session 与 `recipe_id` 关联，只接收 V1 的 `recipe_id`。
- 消息请求只接收 `content`，移除旧接口的 `message` 和扩展字段。
- Fake LLM 支持普通问答和菜谱修改：普通问答不修改版本，修改后版本加一。
- SSE 只产生 `token`、`recipe_updated`、`done`、`error` 四类事件。

## 验证命令与结果

```text
python -m ruff check <本次 Recipe/Chat 文件>
结果：All checks passed

python -m pytest -q tests/test_recipe_schema.py tests/test_recipe_service.py tests/test_chat_recipe.py tests/test_recipe_chat_api.py
结果：15 passed
```

重点断言：

- 普通问答：`token -> done`，菜谱保持 `version=1`。
- 修改请求：`token -> recipe_updated -> done`，菜谱更新为 `version=2`。
- SSE 中不存在 `tool_call` 或 `tool_result`。
- 未确认食材返回 422，模型不可用映射为 503。

## AI 工具与本人检查

AI 用于梳理 V1 契约、生成初始实现和测试骨架。本人逐项检查了请求字段、响应字段、错误状态、版本规则、SSE 事件集合及用户数据隔离，并通过自动化测试复核。

## 未完成与风险

- 黄小石负责的目标检测模型尚未提供，当前只保留确认食材 Repository 接口和模拟数据入口。
- `.env` 和模型权重未加入 Git。
