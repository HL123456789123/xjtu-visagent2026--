# Day1 V1 接口契约审计

## 审计信息

- 检查时间：2026-07-15 09:52:28 +08:00
- 检查人：闫灿宇（项目经理、接口契约与系统集成负责人）
- 当前分支：`feature/project-integration`
- 当前 Commit：`98ed42311139518e1fc66cdcd0255055f3d8b973`
- 唯一接口标准：`docs/contracts/api_v1.md`
- 审计方式：静态读取 FastAPI 路由、对外请求/响应模型、模型输出、SSE、前端 API/入口和 Git 跟踪状态
- 执行边界：本次不修改业务代码，不修改 V1，不执行 Commit、Push、PR、合并或分支操作

## 发布文件检查

以下文件均存在；详细计划的实际文件名与通配要求匹配，无需复制或改名。

| 文件 | 结果 | Git 状态 |
| --- | --- | --- |
| `docs/contracts/api_v1.md` | 存在 | 被 `.gitignore:49` 的 `docs/` 规则忽略，当前未跟踪 |
| `project_docs/00-项目发布说明与执行红线.md` | 存在 | 当前未跟踪 |
| `project_docs/02-已有代码与创新对齐说明.md` | 存在 | 当前未跟踪 |
| `project_docs/03-已有代码对齐检查表.md` | 存在 | 当前未跟踪 |
| `project_docs/任务分工速查表_最终对齐版.md` | 存在 | 当前未跟踪 |
| `project_docs/食物识别菜谱平台_五天并行开发计划_最终对齐详细版.md` | 存在 | 当前未跟踪 |
| `project_docs/成员个人计划/闫灿宇_五天个人任务计划.md` | 存在 | 当前未跟踪 |

## 已发现的现有 API

### 当前已注册路由

`backend/main.py` 当前注册：`auth_router`、`health_router`、`training_router`、`detection_router`、`chat_router`、`dashboard_router`、`camera_router`、`knowledge_router`。

| 模块 | 当前对外路径 |
| --- | --- |
| 根入口 | `GET /` |
| Auth | `POST /api/auth/register`；`POST /api/auth/login`；`GET /api/auth/me`；`POST /api/auth/logout` |
| Health | `GET /api/health`；`GET /api/health/database`；`GET /api/health/redis`；`GET /api/health/minio` |
| Detection | `POST /api/detection/single`；`POST /api/detection/batch`；`POST /api/detection/folder`；`POST /api/detection/video`；`GET /api/detection/tasks/{task_id}`；`GET /api/detection/tasks/{task_id}/results`；`GET /api/detection/tasks`；`GET/POST /api/detection/scenes` |
| Training | `POST /api/training/tasks`；任务 start/pause/cancel/validate；任务详情/status/metrics/list；数据集 validate/split/generate-yaml/格式转换；模型 upload/download |
| Chat | `POST /api/chat/sessions`；`POST /api/chat/sessions/{session_id}/messages`；`GET /api/chat/sessions/{session_id}/messages`；`GET /api/chat/sessions`；`DELETE /api/chat/sessions/{session_id}` |
| Dashboard | `GET /api/dashboard/stats`；`GET /api/dashboard/user-stats` |
| Camera | `WS /api/camera/detect`；`GET /api/camera/scenes` |
| Knowledge | `POST /api/knowledge/upload`；`GET /api/knowledge/search`；`GET /api/knowledge/stats`；`DELETE /api/knowledge/` |

### 旧接口检查

- 未发现精确路径 `/api/detect`。
- 未发现精确路径 `/api/recipe/generate`。
- 存在旧通用检测接口族 `/api/detection/*`。它不是 V1 Food API，不能直接作为前端 V1 公开接口继续使用。
- 当前 `/api/chat/*` 与 V1 路径重叠，但契约内容仍是旧实现，不能视为已完成 V1 Chat。

## 与 V1 一致的内容

| 检查项 | 当前结论 |
| --- | --- |
| API 总前缀 | 现有业务路由统一位于 `/api` 下 |
| 登录身份 | 当前 Chat 使用 `current_user`，客户端未上传 `user_id` |
| 通用成功包络 | 已有 `ApiResponse` 包含 `code`、`message`、`data` |
| Chat 路径参数 | `session_id` 使用整数 |
| 检测基础字段 | 已有检测结果包含 `class_name` 和 `confidence` |
| 固定后端文件 | `backend/app/api/chat.py` 已存在 |
| 固定前端文件 | `frontend/src/api/chat.js`、`frontend/src/utils/stream.js` 已存在 |
| 敏感内容跟踪 | 未发现 Git 跟踪的 `.env`、`best.pt`、常见模型/压缩数据文件、10 MB 以上大对象或高置信度密钥模式 |

上述“一致”只表示单项满足，不代表所在模块整体已符合 V1。

## 与 V1 不一致或尚未实现的内容

| ID | 等级 | 问题与证据 | Owner | 建议处理 |
| --- | --- | --- | --- | --- |
| C-01 | P0 | 唯一契约 `docs/contracts/api_v1.md` 被 `docs/` 忽略且未跟踪；发布说明和个人计划也未进入当前 Git 历史 | 闫灿宇 | 不改契约内容；单独处理 Git 发布范围。优先收窄忽略规则，若暂不改规则则显式强制暂存指定文档 |
| C-02 | P0 | `backend/app/api/food.py` 不存在；`POST/GET/PUT /api/food/recognitions...` 均未实现，`backend/main.py` 未注册 Food 路由 | 绕家辉；入口接线：闫灿宇 | 新建唯一 V1 Food 边界；内部可复用旧检测服务，但必须通过 Adapter 转为 V1，不暴露第二套 Food 接口 |
| C-03 | P0 | `backend/app/api/recipes.py` 不存在；`POST/GET /api/recipes...` 未实现；未发现 Recipe V1 数据结构 | 陈煜君；入口接线：闫灿宇 | 按固定文件名建立 V1 API/Schema；可保留内部生成逻辑，但外层只输出 V1 |
| C-04 | P0 | Recipe 字段 `cooking_time_minutes`、`carbohydrates_g`、`nutrition_disclaimer` 和菜谱 `version` 未出现在 Recipe 实现中 | 陈煜君；前端展示：李晨宁 | 由 Recipe owner 在固定 Schema/响应层实现；不要在入口层临时拼第二套字段 |
| C-05 | P0 | `POST /api/chat/sessions` 当前接收可选查询参数 `title`、返回 HTTP 200 和 `session_uuid/title`；V1 要求 JSON `recipe_id`、HTTP 201 | 陈煜君；`recipe_id` 数据关系：绕家辉 | 优先在现有 Chat API 边界做小范围契约修改/Adapter；数据库关系交数据库 owner |
| C-06 | P0 | 消息请求当前使用 `{"message": ...}`，V1 使用 `{"content": ...}` | 陈煜君；前端：李晨宁 | 后端请求 DTO 与前端 API 封装共同切到 V1；不长期兼容两个公开字段 |
| C-07 | P0 | SSE 当前只发送 `data:`，把类型放在 JSON `type` 中；存在 `tool_call`、`tool_result`；没有 `recipe_updated`；`done` 不含 `message_id`；`error` 不含 V1 `code/message` | 陈煜君；前端解析：李晨宁 | 在 SSE 输出边界 Adapter 为 `event: token/recipe_updated/done/error`；删除公开的工具事件，内部工具调用可保留 |
| C-08 | P0 | `frontend/src/utils/stream.js` 忽略 `event:`，依赖 `[DONE]`、EOF 和通用 `onMessage`；`ChatPage.vue` 仍解析 `data.type` 和 `tool_call` | 李晨宁 | 小范围修改 SSE 解析层，只接受四类 V1 事件；`recipe_updated` 后重新 GET Recipe |
| C-09 | P0 | 当前检测输出为 `class_name`、`confidence`、`bbox: [x1,y1,x2,y2]`；V1 `ModelDetection.bbox` 必须是对象 `{x1,y1,x2,y2}` | 黄小石；模型到 Food API Adapter：绕家辉 | 保留内部数组表示，在 Provider/API 边界转为固定对象，并用 canonical fixture 校验 |
| C-10 | P0 | 四个 canonical fixture 均不存在：food success/empty、recipe success、SSE recipe update | 吴雯 | 只建立 V1 唯一 fixture，前后端 Mock 和契约测试共用 |
| C-11 | P0 | V1 业务错误码均未发现；通用异常当前返回 `detail`，没有 V1 的 `data: null` 约束 | Food：绕家辉；Recipe/Chat：陈煜君；共享入口协调：闫灿宇 | 各业务 owner 在边界映射固定错误码；如需改共享异常处理器，先提交接线需求，不放宽 V1 |
| C-12 | P0 | 前端缺少 `food.js`、`recipe.js`；当前 router/sidebar 只有旧 Chat、Detection、Training、History、Dashboard、Profile，没有 Food 识别确认和 Recipe 展示入口 | Food 前端：刘楚涵；Recipe/Chat 前端：李晨宁；入口：闫灿宇 | 等页面 owner 提供组件与目标路由后，由闫灿宇统一小范围接线；不在入口文件实现业务逻辑 |

## SSE 事件专项结论

- V1 允许：`token`、`recipe_updated`、`done`、`error`。
- 当前可见：JSON `type=token/done/error/tool_call/tool_result`，但不是标准 SSE `event:` 形式。
- 当前缺失：`recipe_updated`。
- 当前违规公开事件：`tool_call`、`tool_result`。
- 未发现作为 SSE 事件的 `message`、`finish`、`complete`。

## Adapter 与小范围修改决策

1. 旧检测服务和 bbox 数组：使用 Adapter，不推倒已有检测实现。
2. 旧 Chat 内部 LangGraph/工具逻辑：内部可保留；API DTO、会话绑定、SSE 输出必须由原 owner 小范围修改或增加边界 Adapter。
3. Food/Recipe 固定文件不存在：按 V1 固定命名新增唯一公开入口，不把 `/api/detection/*` 包装成第二套长期公开 API。
4. `backend/main.py`、router、sidebar：只做入口接线，必须等待业务 owner 交付并提供接线信息。
5. V1 契约、业务 DTO、ORM、migration、LangGraph 核心、Chat 页面和 Docker 文件：本次均不直接修改。

## 审计结论

当前仓库具备旧 VisAgent 通用骨架和部分可复用内部能力，但尚未形成 V1 Food → Recipe → Chat 主链路。Day3 Mock 前必须先解决 C-01 至 C-12 中的契约发布、固定路由/Schema、SSE、fixture 和入口接线问题；所有业务偏差退回对应 owner，闫灿宇只负责契约检查和共享入口接线。
