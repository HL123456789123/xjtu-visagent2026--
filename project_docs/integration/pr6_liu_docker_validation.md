# 刘楚涵：PR6 完整 RC Docker 独立验收说明

## 目的与边界

本说明用于在**另一台电脑**上独立验证完整候选分支 `release/pr6-full-docker-rc`。不要复制主电脑的项目目录、虚拟环境、数据库卷、`.env` 或任何 API Key。

- 首轮固定使用 `FOOD_PROVIDER=mock`、`LLM_MODE=fake`。
- 不需要、不得索取或填写他人的智谱 API Key。
- 第二轮才验证本地 YOLO 权重；LLM 仍保持 `fake`。
- `best.pt` 和模型压缩包不进入 Git；只通过 GitHub Release `food-model-v1.0` 获取。
- Docker 验收仅报告实际结果，不因页面可打开就写成全链路通过。

## 1. 获取唯一候选基线

在自己的空目录执行：

```powershell
git clone https://github.com/HL123456789123/xjtu-visagent2026--.git visagent-pr6-rc
cd visagent-pr6-rc
git fetch --all --prune
git switch -c release/pr6-full-docker-rc --track origin/release/pr6-full-docker-rc
git log -1 --oneline
git status --short
```

验收前工作区应干净。不要切换到 PR #4、#5、#6、#8、#11 或 #12 的旧分支，也不要 cherry-pick 旧提交。

## 2. 下载并核验模型（第二轮 YOLO 前完成）

先确认 GitHub CLI 已登录到有仓库读取权限的账号，再从仓库根目录执行：

```powershell
gh auth status
.\scripts\download_food_model.ps1
git check-ignore -v models/food/best.pt
git status --short
```

脚本会下载 `food-model-v1.0` Release、校验压缩包和以下成对制品、比较 Release 与仓库跟踪的 `classes.yaml`，最后仅将权重放入本地 `models/food/best.pt`：

```text
best.pt       19,194,771 bytes
SHA-256       680accafc8c22854b37e959106c37a44b3e8c42b4d260d7f3c4681021c2a31cd

classes.yaml         640 bytes
SHA-256       8bd06c89afe18fbb6bf7d64d44b51f84f8199a80678e63123f35c09fd6c9913b
```

任一校验失败时停止；不要手动替换仓库中的 `backend/scripts/food_model/classes.yaml`，也不要把 `best.pt` 暂存或提交。

## 3. 创建自己的本地 Docker 配置

根目录模板是 `.env.example`。只在自己的电脑创建被忽略的 `.env`：

```powershell
Copy-Item .env.example .env
```

编辑 `.env` 时，首轮至少使用各自本机生成的数据库、MinIO、JWT 值，并保持：

```dotenv
FOOD_PROVIDER=mock
LLM_MODE=fake
FOOD_CONF_THRESHOLD=0.25
```

不要把 `.env`、真实密码、Token 或任何 LLM Key 发到群里、截图中或 Git。首轮不需要 `LLM_API_KEY`；占位值不会触发真实 LLM 调用。

第二轮 YOLO/Fake 仅修改为：

```dotenv
FOOD_PROVIDER=yolo
FOOD_MODEL_PATH=/models/food/best.pt
FOOD_CLASSES_PATH=/app/backend/scripts/food_model/classes.yaml
FOOD_CONF_THRESHOLD=0.25
LLM_MODE=fake
```

## 4. Compose 静态检查、构建与启动

使用独立项目名，避免影响电脑上其他 Compose 项目：

```powershell
docker version
docker compose version
docker compose -p visagent-pr6-rc config
docker compose -p visagent-pr6-rc build
docker compose -p visagent-pr6-rc up -d
docker compose -p visagent-pr6-rc ps
docker compose -p visagent-pr6-rc logs --tail=200 postgres redis minio backend frontend
```

服务应包含 `postgres`、`redis`、`minio`、`backend`、`frontend`。预期端口为前端 `3000`、后端 `8888`、MinIO `9000/9001`；数据库迁移由后端容器启动命令执行。可以额外确认：

```powershell
Invoke-WebRequest http://127.0.0.1:8888/api/health
Invoke-WebRequest http://127.0.0.1:8888/docs
docker compose -p visagent-pr6-rc exec backend uv run --no-sync alembic heads
docker compose -p visagent-pr6-rc exec backend uv run --no-sync alembic current
```

如果服务未健康，不要用 `docker system prune`、不要删除其他项目卷；记录第一个失败服务及其日志即可。

## 5. 首轮 Mock/Fake 页面验收

浏览器打开 `http://127.0.0.1:3000`，应出现 FridgeChef 登录页和顶部导航。自行注册普通测试用户；不要在源码、文档或报告里写固定账号密码。

按顺序实际操作并记录结果：

1. 登录后进入首页，确认顶部导航、Food 页面、菜谱/对话入口、历史记录、训练、个人中心可访问。
2. 普通用户不应看到“管理后台”；直接输入管理员 URL 应被前端守卫拒绝，普通用户请求管理员 API 应返回 `403`。
3. Food 页面一次选择两张可公开使用的 JPG/PNG；确认请求字段只有 `images`，返回 `images` 数组且候选按 `image_index` 关联。
4. Mock Provider 可以返回空候选；手工添加并确认食材后，生成 Recipe `version=1`，检查完整字段和营养免责声明。
5. 创建 Chat：普通问题应产生 `token → done`，Recipe 版本不变；“改成三人份并少放油”应产生 `token → recipe_updated → done`，Recipe 变为 `version=2`。
6. 刷新浏览器、切换 Food/Recipe/Chat/History 页面，再回到 Recipe/Chat；重启后端容器后再次检查已创建数据的可恢复性。

第 6 项是发布门禁：若 API 数据存在但页面没有恢复入口，也要报告为“页面恢复/历史入口失败”，不得以 localStorage 假装后端历史已实现。

## 6. 第二轮 YOLO/Fake 验收

完成模型下载后按第 3 节修改为 YOLO/Fake，再执行：

```powershell
docker compose -p visagent-pr6-rc up -d --force-recreate backend
docker compose -p visagent-pr6-rc ps
docker compose -p visagent-pr6-rc logs --tail=200 backend
```

上传 Release 中的 `demo_multi_food.jpg`。在 `conf=0.25` 下，预期项目 Provider 返回 6 个目标：`milk`、两处 `sugar`、`butter`、`banana`、`corn`。每个候选必须有合法的 `bbox.x1/y1/x2/y2` 和 `image_index`；确认食材后重复 Recipe v1 与 Chat v2 流程。

若模型目录为空或 hash 不正确，真实 YOLO 应返回 `503 / FOOD_MODEL_UNAVAILABLE`，不得静默改成 Mock 后写成 YOLO 通过。

## 7. 失败报告格式

发生失败时收集以下信息（绝不包含 `.env`、密码、Token、Authorization 头或模型文件）：

```text
RC commit:
验收轮次: Mock/Fake 或 YOLO/Fake
操作系统与 Docker/Compose 版本:
执行命令与工作目录:
第一个失败步骤:
预期结果:
实际状态码/页面现象:
docker compose ps:
相关服务最近 200 行脱敏日志:
是否已核验模型 Hash:
是否可稳定复现:
```

停止服务时只处理本项目：

```powershell
docker compose -p visagent-pr6-rc down
```

不要删除命名卷，除非负责人明确要求重建本项目的测试数据。
