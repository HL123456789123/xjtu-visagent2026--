# 陈煜君 Day 4：真实 LLM

## 今日完成

- 增加 OpenAI-compatible LLM Gateway，使用 `OPENAI_BASE_URL`、`OPENAI_API_KEY`、`OPENAI_MODEL`。
- 支持 `LLM_MODE=fake|real` 和 1–300 秒超时配置。
- 真实模式失败时返回 `LLM_UNAVAILABLE`，不会自动回退 Fake。
- Recipe 和 Chat 输出均通过 Pydantic 严格校验，拒绝额外字段和不完整菜谱。
- `generator` 正确保存 `provider/model/is_mock`。
- 本地 `.env` 使用老师提供的 SiliconFlow 配置，但密钥不写入源码、日志或提交。

## 真实接口验证

第一次调用结果：模型返回“菜名、份数”等中文键名，被 Pydantic 拒绝为非法结构。随后在固定 Prompt 中加入精确英文 JSON Schema，再次验证成功。

成功结果摘要：

```json
{
  "generator": {
    "provider": "openai_compatible",
    "model": "Qwen/Qwen3.6-35B-A3B",
    "is_mock": false
  },
  "recipe_title": "清淡版番茄炒蛋",
  "recipe_servings": 2,
  "chat_action": "update_recipe",
  "updated_servings": 3
}
```

缺失 Key 场景通过自动化测试验证：真实模式初始化直接抛出 `LLMUnavailableError`，API 映射为 HTTP 503。

## AI 工具与本人检查

AI 用于补全兼容调用、JSON Prompt 和异常映射。本人检查了真实返回内容、结构校验失败原因、真实生成元数据、三人份修改结果及“失败不回退”行为。

## 风险

- 老师提供的 API Key 曾出现在聊天内容中，建议演示结束后轮换。
- 真实模型单次响应可能耗时一至两分钟，当前超时为 60 秒，可按现场网络调整但不应超过 300 秒。
