# Day 5：回归、Docker 配置与答辩证据

> 完成日期：2026-07-15。

## 实际执行命令与结果

```powershell
cd backend
$env:DEBUG='false'; uv run pytest tests/test_food_recognition.py -q
```

结果：`15 passed`。覆盖 V1 fixture、Food API、原图读取、413、415、503、跨用户 403、确认覆盖、三个 Repository、Mock Provider、YOLO 不可用、YOLO 初始化失败映射和 migration 升降级。

```powershell
cd backend
$env:DEBUG='false'; uv run pytest -q
```

结果：`103 passed, 2 warnings`。警告来自 Starlette TestClient 和 Pydantic V2 配置迁移，不是失败。

```powershell
docker compose config
```

结果：配置成功解析，确认 backend 包含：

- `FOOD_PROVIDER`、`FOOD_MODEL_PATH`、`FOOD_CLASSES_PATH`；
- `./models/food:/models/food:ro`；
- 先执行 `alembic upgrade head` 再启动 Uvicorn。

## 本人检查

- 主应用 OpenAPI 已包含三条 V1 Food API，不再是仅测试应用中的临时路由。
- 错误响应统一为 `{code, message, data}`，Food 已覆盖 403、413、415、503。
- `DEBUG=release` 已被配置兼容层识别为 `false`，避免测试导入期失败。

## Docker 证据状态

`docker compose ps` 返回 Docker Desktop Linux Engine 未启动；因此本机未执行容器级 Food 主流程。Docker daemon 启动并提供 `models/food/best.pt` 后，应执行：

```powershell
$env:FOOD_PROVIDER='yolo'
docker compose up --build -d
docker compose ps
docker compose logs backend
```

随后使用登录后的 JPG/PNG 调用 Food API，检查 PostgreSQL 记录、MinIO 对象和 yolo 返回值。
