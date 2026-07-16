# 陈煜君 Day 5：回归、Docker 与答辩证据

## 今日完成

- PostgreSQL、Redis、MinIO 容器启动并通过容器健康检查。
- Alembic 从空数据库完整升级到 `17f47c61a21b (head)`。
- 真实 HTTP 链路完成：注册、登录、JWT、模拟确认食材、生成、查询、普通问答、修改和再次查询。
- 修复 Dockerfile 中已失效的 Debian 软件包名，并增加 `.dockerignore`，确保 `.env`、虚拟环境、模型和运行数据不进入镜像。
- 补齐 Day 3–5 日志和 Recipe/Chat 答辩说明。

## 真实 HTTP 结果

```json
{
  "recipe_status": 201,
  "query_status": 200,
  "generator": {
    "provider": "openai_compatible",
    "model": "Qwen/Qwen3.6-35B-A3B",
    "is_mock": false
  },
  "answer_events": ["token", "done"],
  "update_events": ["token", "recipe_updated", "done"],
  "initial_version": 1,
  "final_version": 2,
  "final_servings": 3
}
```

目标检测尚未接入，因此本次验证直接向 `food_recognition_tasks.confirmed_ingredients` 写入番茄和鸡蛋，模拟 Food API 完成“用户已确认食材”后的交接状态。

## 回归测试

- 本次 Recipe/Chat 范围：15 passed。
- 全量后端：108 passed，11 failed，共 119 项。
- 11 个失败均位于既有 Dashboard/Training 认证测试和 MinIO 健康测试：认证测试登录成功后返回空 Header，后续请求得到 401；不属于本次 Recipe/Chat 改动。

## Docker 证据

- 第一次构建失败：`libgl1-mesa-glx` 在当前 Debian 源中已不可用。
- 改为 `libgl1` 后系统依赖步骤通过。
- `.dockerignore` 将构建上下文从约 364 MB 降至约 0.3 MB，并排除 `.env`。
- 深度学习依赖冷构建运行 15 分钟后命令超时，缓存约 6.6 GB，最终镜像尚未生成。该项如实保留为未完成证据。

## AI 工具与本人检查

AI 用于执行回归、定位真实模型字段偏差、编写验证脚本和整理证据。本人检查了数据库迁移结果、HTTP 状态、SSE 事件顺序、版本变化、真实模型标记、密钥忽略状态和 Docker 构建日志。

## 剩余事项

- 接入黄小石的 FoodRecognitionProvider 后，删除验证脚本中的模拟确认食材步骤。
- 使用已有 Docker 缓存继续完成后端镜像构建。
- Dashboard/Training 的 11 个既有失败交由对应模块负责人处理。
