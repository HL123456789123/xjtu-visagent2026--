# VisAgent 答辩交付冲刺验收报告

**日期：** 2026-07-19
**工作分支：** `codex/food-history-showcase`
**验证范围：** 本机 Docker Compose、Mock/Fake 与 YOLO/Real LLM 两轮、历史与持久化、权限隔离。
**结论：** 主链路具备答辩演示条件；这不是“最终发布通过”声明，训练材料与六目标官方演示图片仍待补齐。

## 1. 运行环境与配置安全

| 项目 | 实际结果 |
| --- | --- |
| 操作系统 | Windows 11（Windows NT 10.0.26200.0） |
| Docker Engine | 29.6.1 |
| Docker Compose | v5.1.4 |
| Git / GitHub CLI | 2.44.0.windows.1 / 2.96.0 |
| Compose 静态检查 | `docker compose -p visagent-history-dev config --quiet` 通过 |
| 镜像构建 | backend、frontend 构建通过；依赖层命中缓存，frontend 完成生产构建且 Nginx 配置被复制 |
| 构建警告 | `@vueuse/core` 的 PURE 注释警告、前端 chunk 大小告警；均未阻断构建 |
| 机密与权重 | `.env` 未被读取、输出或提交；`models/food/best.pt` 被 Git 忽略且未跟踪；前端本地日志未纳入提交 |

## 2. 服务、迁移与基础检查

| 服务 | 结果 |
| --- | --- |
| postgres | healthy |
| redis | healthy |
| minio | healthy |
| backend | healthy，`/api/health` 返回 200，`/docs` 可访问 |
| frontend | running，根页面返回 200 |
| Alembic | 单一 head：`a7e1c9f42d6b`；current 与 head 一致 |

## 3. 自动化检查

| 检查 | 实际结果 |
| --- | --- |
| 后端静态检查 | `uv run ruff check app/` 通过 |
| 后端全量测试 | `179 passed`；使用独立 `visagent_test` 数据库 |
| 前端单元测试 | `122 passed`，16 个测试文件 |
| 前端生产构建 | `bun run build` 通过 |
| 损坏图片防护 | 截断 PNG 返回 `422 / INVALID_IMAGE_CONTENT`，且在进入 YOLO 前被拦截 |

## 4. Mock/Fake Docker 链路

运行脚本：[run_mock_fake_validation.ps1](run_mock_fake_validation.ps1)。

| 验证项 | 实际结果 |
| --- | --- |
| 多图上传 | 201；2 张图片，`image_index` 为 `0,1` |
| 食材确认 | 2 项确认食材 |
| 菜谱与会话 | Fake 菜谱 version 1；修改对话后 version 2 |
| SSE | 含 `token`、`recipe_updated`、`done`；未见旧事件名 |
| 历史与个人看板 | 均可查询到本用户数据 |
| 普通用户管理员 API | `/api/admin/users` 返回 403 |
| 重启后读取 | backend 重启后仍能读取 Recipe version 2 |

## 5. YOLO/Real LLM Docker 链路

运行脚本：[run_yolo_real_validation.ps1](run_yolo_real_validation.ps1)。

| 验证项 | 实际结果 |
| --- | --- |
| 实际 Provider | `yolo`，模型状态 `available=true`，类别数 12；未静默切换 Mock |
| 实际 LLM | 结构化菜谱生成成功，`is_mock=false` |
| YOLO 上传 | 201；替代演示图返回 1 个合法 bbox，`image_index=0` |
| Recipe / Chat | v1 创建成功；真实 LLM 修改对话后 v2；SSE 为 `token → recipe_updated → done` |
| 缺失权重防护 | 临时切换不存在权重路径后，识别接口返回 503；随后恢复真实权重 |
| 重启与持久化 | backend 重启、`docker compose down`（未使用 `-v`）后重新 up，均可读回 Recipe version 2 |

## 6. 历史与角色 P0 复验

| 项目 | 结果 |
| --- | --- |
| P0-1：历史恢复 | 数据库/API 层在页面切换相关链路、backend 重启及 Compose down/up 后仍保留 Recipe v2；前端已有按 recipe id 恢复入口与会话恢复逻辑，不依赖 localStorage。相关前端测试已通过。 |
| P0-2：角色显示 | 用随机临时管理员账号验证：`/api/auth/me` 包含 admin 角色、管理员 API 返回 200、Profile 页面显示“管理员”、导航出现管理员入口。验证账号及关联数据已删除。 |
| 普通用户隔离 | 普通用户的管理员 API 为 403；历史与看板接口按用户范围返回。 |

角色展示截图索引：[01-admin-profile-role.png](evidence/01-admin-profile-role.png)。

## 7. 模型 Release 与材料状态

| 项目 | 实际结果 |
| --- | --- |
| Release | `food-model-v1.0`；资产为 `visagent-food-model-v1-yolo11s.zip` 与 `SHA256SUMS.txt` |
| best.pt | 19,194,771 bytes；SHA-256 `680accafc8c22854b37e959106c37a44b3e8c42b4d260d7f3c4681021c2a31cd` |
| classes.yaml | 640 bytes；SHA-256 `8bd06c89afe18fbb6bf7d64d44b51f84f8199a80678e63123f35c09fd6c9913b` |
| Release ZIP | GitHub Release 标注 SHA-256 `9c324d05a77b4d9940c9558b6de53b640a6d3543f1486614521fd2bc90168d29` |
| 六目标演示 | `demo_multi_food.jpg` 不在当前 Release 资产或仓库中，无法复验 milk、sugar×2、butter、banana、corn 共 6 个目标；这是待补交演示材料，不记为 Docker 构建失败。 |
| 训练展示材料 | 未收到 `data.yaml`、训练/验证/测试数量、类别分布、`results.csv`、训练参数、最终指标和脱敏样例；训练页保持真实运行模型状态与真实空状态，不伪造曲线。 |

## 8. 脱敏日志摘录与首个新问题

```text
backend  health check: HTTP 200
frontend root page: HTTP 200
food model status: provider=yolo, available=true, class_count=12
invalid image: HTTP 422, detail=INVALID_IMAGE_CONTENT
missing model path: HTTP 503
recipe after restart: version=2
```

本轮没有发现新的 Docker 阻断问题。最早出现的非阻断项为 frontend 构建中的依赖注释与 chunk 体积警告；它们不影响镜像构建和运行，但可在答辩后作为前端性能优化项处理。

## 9. 复验步骤

1. 从仓库根目录运行 `docker compose -p visagent-history-dev up -d`。
2. 在本地安全环境中配置实际 YOLO 权重路径；需要展示真实 LLM 时，再在本机私有环境中配置 Key。
3. 运行 `powershell -NoProfile -ExecutionPolicy Bypass -File project_docs/defense/run_mock_fake_validation.ps1`。
4. 运行 `powershell -NoProfile -ExecutionPolicy Bypass -File project_docs/defense/run_yolo_real_validation.ps1`。
5. 补齐黄小石材料后，使用官方 `demo_multi_food.jpg` 复验六目标，并将真实训练材料接入训练展示。

## 10. 当前交付判断

- 可以进入“P0 修复后的第二轮复验”与答辩演示排练。
- 不应声称已最终发布通过：官方六目标演示图片和训练展示材料尚未交付，真实 LLM 也仍依赖第三方网络与本机私有配置。
