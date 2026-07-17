# Recipe / Chat 模块答辩说明

## 我的职责

我负责确认食材之后的菜谱生成、菜谱查询、基于菜谱的对话修改、最小 LangGraph、LLM 结构校验和四类 SSE。目标检测模型本身不属于本模块。

## 输入与输出

Recipe 输入为 `recognition_id` 和用户偏好。后端必须按当前用户读取已确认食材，未确认时返回 422。输出为完整结构化菜谱、营养估算、免责声明、版本和生成器信息。

Chat 创建会话时只接收 `recipe_id`；消息只接收 `content`。普通回答不改版本，修改菜谱时保存完整新版本并令 `version + 1`。

## 最小 LangGraph

首次生成：

```text
load_confirmed_ingredients -> generate_recipe -> validate_and_save
```

菜谱对话：

```text
load_recipe_context -> call_llm -> answer / update_recipe
```

没有增加 Supervisor、工具调用或知识库，避免超出五天 MVP。

## 错误处理

- 识别记录不存在：404。
- 未确认食材：422。
- LLM JSON 或结构非法：422。
- LLM 缺少 Key、超时或上游失败：503，且不回退 Fake。
- 用户访问他人菜谱：403。

## SSE

只允许四类事件：`token`、`recipe_updated`、`done`、`error`。普通问答不发送 `recipe_updated`；修改成功后前端收到菜谱 ID 和新版本，再调用 Recipe 查询接口刷新页面。

## 本人验证

- 15 项 Recipe/Chat 自动化测试通过。
- Alembic 全链迁移成功。
- 使用真实 Qwen 模型生成两人份菜谱，再通过 Chat 修改为三人份少油版本。
- 实际 HTTP 结果为 Recipe 201、查询 200、版本 1 到 2。

## AI 使用说明

AI 帮助整理契约、生成实现草稿、补充测试和定位 Docker/模型返回问题。本人负责确认所有公开字段、状态码、权限、版本、SSE 顺序和真实运行结果，并保留未完成项。
