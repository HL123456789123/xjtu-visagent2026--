# Day1 接线检查清单

> 唯一接口标准：`docs/contracts/api_v1.md`。本清单只描述入口接线条件，不授权修改业务 owner 的核心实现。

## 一、后端入口

### `backend/main.py` 最终需要注册的 V1 路由

| V1 路由 | 固定来源文件 | 当前状态 | 业务 Owner | 入口 Owner |
| --- | --- | --- | --- | --- |
| Food：`/api/food` | `backend/app/api/food.py` | 文件及路由均不存在，等待交付 | 绕家辉 | 闫灿宇 |
| Recipe：`/api/recipes` | `backend/app/api/recipes.py` | 文件及路由均不存在，等待交付 | 陈煜君 | 闫灿宇 |
| Chat：`/api/chat` | `backend/app/api/chat.py` | 已注册，但仍是旧契约，不能作为 V1 验收 | 陈煜君 | 闫灿宇 |

### 当前已经注册的路由

- `auth_router`
- `health_router`
- `training_router`
- `detection_router`
- `chat_router`
- `dashboard_router`
- `camera_router`
- `knowledge_router`

### 后端接线动作

- [ ] 绕家辉完成 `food.py`，提供 router 导出名、V1 路径和最小契约测试结果。
- [ ] 陈煜君完成 `recipes.py`，提供 router 导出名、V1 路径和最小契约测试结果。
- [ ] 陈煜君将现有 `chat.py` 对齐 V1 会话请求、消息请求和四类 SSE。
- [ ] 绕家辉确认 ChatSession 的 `recipe_id` 数据关系已由唯一 migration 支持。
- [x] 吴雯已通过 PR #1 提供 canonical fixture 与 fixture 契约测试，复审通过并已合入 `develop`。
- [ ] 闫灿宇在上述条件满足后，只在 `backend/main.py` 增加 Food/Recipe 路由导入和注册，并复核 Chat 注册未重复。
- [ ] 保留旧路由时确认它们不被前端当作第二套 Food/Recipe/Chat 公开接口。

## 二、前端入口

### Router 需要接入的功能页面

| 功能页面 | 当前状态 | 页面/API Owner | 接线 Owner | 接线前置条件 |
| --- | --- | --- | --- | --- |
| 登录/注册 | `LoginPage.vue`、`RegisterPage.vue` 已存在 | 现有模块 | 闫灿宇 | 保持当前认证守卫可用 |
| Food 上传、候选编辑与食材确认 | 当前只有通用 `DetectionPage.vue`，不能视为 V1 Food 页面 | 刘楚涵 | 闫灿宇 | Owner 提供最终组件路径、建议前端路由和 `food.js` |
| Recipe 结构化展示 | 未发现 V1 Recipe 页面或 `recipe.js` | 李晨宁 | 闫灿宇 | Owner 提供最终组件路径、recipe_id 传递方式和页面路由 |
| Recipe 智能对话 | `ChatPage.vue` 已存在但使用旧会话/SSE 契约 | 李晨宁 | 闫灿宇 | Owner 完成 V1 `chat.js`、四类 SSE 和 `recipe_updated` 后重新 GET |
| 个人信息 | `ProfilePage.vue` 已存在 | 现有模块 | 闫灿宇 | 非 V1 主链路阻断项 |

V1 未冻结具体前端 URL 和页面文件名，因此入口负责人不自行发明路径；以页面 owner 的接线需求为输入，再统一落到 `frontend/src/router/index.js`。

### Sidebar 需要接入的菜单

- [ ] “食物识别/食材确认”入口：指向刘楚涵交付的 V1 Food 页面。
- [ ] “菜谱/智能对话”入口：指向李晨宁交付的 Recipe 展示或绑定 Recipe 的 Chat 页面。
- [ ] 评估现有“目标检测”“模型训练”“历史记录”“仪表盘”是否属于 MVP 主导航；本轮只登记，不擅自删除。
- [ ] 菜单标题、图标和顺序由闫灿宇统一接线，但不在 sidebar 内实现业务状态。

### 当前 Router 页面路由

- `/login` → Login
- `/register` → Register
- `/chat` → Chat
- `/detection` → Detection
- `/training` → Training
- `/history` → History
- `/dashboard` → Dashboard
- `/profile` → Profile
- `/` 当前重定向到 `/chat`

### 当前 Sidebar 菜单

- 智能对话
- 目标检测
- 模型训练
- 历史记录
- 仪表盘
- 个人信息

## 三、集成准备

### Day3 Mock 前缺少什么

- [x] `docs/contracts/api_v1.md` 已通过 PR #2 进入 `develop`，成为仓库内唯一接口标准。
- [ ] `backend/app/api/food.py` 与 Food V1 三个接口。
- [ ] `backend/app/api/recipes.py` 与 Recipe V1 两个接口。
- [ ] Chat 会话绑定 `recipe_id`，消息体改为 `content`。
- [ ] SSE 仅输出 `token`、`recipe_updated`、`done`、`error`，并具备正确 data 字段。
- [ ] `frontend/src/api/food.js`、`recipe.js`、V1 `chat.js`。
- [ ] Food 页面、Recipe 展示页面、V1 Chat 页面/解析层交付接线信息。
- [x] 四个 canonical fixture 已通过 PR #1 合入：Food success/empty、Recipe success、SSE recipe update。
- [ ] Mock Food Provider 和 Fake LLM 明确返回 `mock/fake` 标记。
- [ ] Recipe 固定字段、整数 ID、版本规则、营养免责声明和 V1 错误码通过契约测试。
- [ ] `recipe_updated` 后前端执行 `GET /api/recipes/{recipe_id}`。
- [ ] 闫灿宇完成 `backend/main.py`、router、sidebar 的一次性共享入口接线。

### Day4 真实接入前缺少什么

- [ ] 黄小石交付 `image_path`/`conf_threshold=0.25` → `list[ModelDetection]` 的真实 Provider。
- [ ] `bbox` 在 Provider/API 边界转换为 `{x1,y1,x2,y2}`。
- [ ] `backend/scripts/food_model/classes.yaml` 与稳定 12 类说明。
- [ ] `best.pt` 仅通过宿主机/Docker 挂载提供，确认未进入 Git。
- [ ] 绕家辉完成真实 YOLO Provider 接入；不可用时返回 `FOOD_MODEL_UNAVAILABLE`/503。
- [ ] 陈煜君完成真实 OpenAI-compatible LLM；不可用时返回 `LLM_UNAVAILABLE`/503，禁止自动切 Fake。
- [ ] 验证 Recipe `version` 从 1 到 2，普通问答不增版本。
- [ ] 验证真实 SSE 的 `token` → `recipe_updated` → `done` 顺序和前端重新 GET。
- [ ] 吴雯在 Docker 环境复跑 V1 全链路并给出验收证据。

## 推荐接线顺序

1. 绕家辉完成 ORM/Repository、Food API 和模型 Adapter。
2. 陈煜君完成 Recipe/Chat API、Schema、Fake/Real LLM 和四类 SSE。
3. 刘楚涵、李晨宁完成固定前端 API 封装和页面。
4. 吴雯提供 canonical fixture 与契约测试结果。
5. 闫灿宇统一修改 `backend/main.py`、router 和 sidebar。
6. Day3 只合入通过契约测试的 Mock 链路；Day4 再替换真实 Provider。

## Day1 测试 PR 合并记录

- canonical fixtures：已完成并进入 `develop`。
- 测试 PR：[#1](https://github.com/HL123456789123/xjtu-visagent2026--/pull/1)。
- 审核结论：复审通过；四个 fixture 符合 V1，4 项 fixture 契约测试通过。
- 合并状态：已合并。
- 合并方式：Squash。
- Squash Commit：`9fffc2f7e373440b58b1daba1e1ccda0d19d8f25`。
- 吴雯临时分支：远程 `chore/test-docker` 已删除。
- 刘楚涵 Food 前端：canonical fixture 阻塞已解除；应从最新 `develop` 同步，并直接使用 Food success/empty fixture，不 cherry-pick 旧 Commit。

### 剩余 Day1 P0

- Food API：等待绕家辉交付固定 V1 路由、Schema、Repository 和模型 Adapter。
- Recipe API：等待陈煜君交付固定 V1 路由、Recipe Schema、Fake/Real LLM 边界。
- Chat/SSE：等待陈煜君、李晨宁将请求体和对外事件收敛为 V1。
- 前端页面：等待刘楚涵、李晨宁交付 Food、Recipe/Chat 页面及接线信息。
- 共享入口：等待上述模块可运行后，由闫灿宇统一接入 `backend/main.py`、router 和 sidebar。
