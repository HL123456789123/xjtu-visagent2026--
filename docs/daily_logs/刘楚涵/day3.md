# 刘楚涵 Day3 个人工作日志

- 日期：2026-07-17
- 分支：`feature/frontend-food-workflow`
- 今日角色：食物识别工作流前端
- 今日目标：接 Mock Food API，加入 Mock 全链路。

## 1. 今天实际完成

- Food 页面默认保留“后端 Mock API”模式，可在 `integration/day3-mock` 后端就绪后直接走真实 HTTP；同时提供“前端 Mock 成功/空识别/错误”用于后端分支缺位时验证前端链路。
- 上传组件新增“使用固定演示图”，固定读取 `/food-carousel-1.jpg` 并转成 `File`，不依赖系统文件选择框。
- 完成 Mock 流程：固定演示图 → 返回候选食材 → 删除误识别项 → 手工新增食材 → 确认食材。
- 确认后保存整数 `recognition_id`，点击“生成菜谱”时调用 Recipe API Mock，传入：
  - `recognition_id`
  - `preferences`
  - 不额外暴露第二套 Food 字段
- 页面展示 Recipe 生成结果，包含结构化菜谱和固定营养免责声明。
- 补充 503 和网络失败提示：
  - Food API fixture 增加 `network` 场景。
  - 页面错误状态区分网络失败、413、415、422、503。
  - `request.js` 和 `uploadRequest` 增加 503 统一提示。
- 补充测试覆盖：固定演示图、网络失败 Mock、Food 确认后 Recipe 生成、`recipe-requested` payload。

## 2. 前置阅读和依据

- 已阅读 `docs/contracts/api_v1.md` 中本人相关章节：
  - 第三节：`IngredientCandidate` / `ConfirmedIngredient` 固定字段。
  - 第五节：Food API 三个接口、`images` 字段、确认食材请求。
  - 第十三节：canonical fixture 共用字段。
- 已提取阅读《04-前端项目初始化.pdf》：
  - Vue 3 + Vite 项目结构、`src/api` 请求封装、`utils/request.js`、组件拆分、路由守卫、`bun run test` / `bun run build`。
- 已提取阅读《06-目标检测功能.pdf》：
  - FormData 上传、多图/批量检测思路、检测结果展示、置信度展示、Canvas/结果表状态处理。
- 已阅读 `D:\2026小学期\食物识别菜谱平台_五天并行开发计划_最终对齐详细版.md` 中刘楚涵 Day3 任务。

## 3. 手测流程和结果

- 启动前端：`bun run dev -- --host 0.0.0.0 --port 3000`
- 启动当前后端用于正常登录：`uv run uvicorn main:app --reload --host 0.0.0.0 --port 8888`
- 登录账号：README 默认普通用户 `user / User@2026`。
- 页面：`http://localhost:3000/food-recipes`
- Mock 场景：`前端 Mock 成功`
- V1 步骤 2 到 5 手测：
  1. 使用固定演示图。
  2. 点击开始识别，得到候选食材：番茄、鸡蛋。
  3. 删除误识别项：鸡蛋。
  4. 手工新增食材：土豆，数量 2，单位 个。
  5. 确认食材，页面显示 `recognition_id: 12`、`confirmed_ingredients: 2 项`。
- Mock E2E：
  - 点击“生成菜谱”后，Recipe Mock 收到 `recognition_id: 12`。
  - 页面展示 `番茄炒蛋`、version 1、食材用量、步骤和营养免责声明。

## 4. 截图证据

- 上传到确认完整截图：`docs/daily_logs/刘楚涵/screenshots/day3-upload-confirm.png`
- Mock E2E 菜谱完整截图：`docs/daily_logs/刘楚涵/screenshots/day3-mock-e2e-recipe.png`
- Mock E2E 菜谱清晰视口截图：`docs/daily_logs/刘楚涵/screenshots/day3-recipe-viewport.png`

## 5. 测试命令和结果

- `bun run test`
  - 结果：13 个测试文件、122 个用例全部通过。
- `bun run build`
  - 结果：构建成功。
  - 备注：仍有 `@vueuse/core` pure annotation warning 和 chunk size warning，非本次改动引入，未阻塞构建。

## 6. 修改文件

- `frontend/src/api/food.js`
- `frontend/src/fixtures/foodRecognition.js`
- `frontend/src/utils/request.js`
- `frontend/src/views/FoodRecipePage.vue`
- `frontend/src/components/food/FoodImageUploader.vue`
- `frontend/src/api/__tests__/food.test.js`
- `frontend/src/components/food/__tests__/FoodImageUploader.test.js`
- `frontend/src/utils/__tests__/request.test.js`
- `frontend/src/views/__tests__/FoodRecipePage.test.js`
- `docs/daily_logs/刘楚涵/day3.md`
- `docs/daily_logs/刘楚涵/screenshots/day3-upload-confirm.png`
- `docs/daily_logs/刘楚涵/screenshots/day3-mock-e2e-recipe.png`
- `docs/daily_logs/刘楚涵/screenshots/day3-recipe-viewport.png`

## 7. AI 辅助内容和本人检查过程

- AI 辅助对照 V1 第三、五、十三节检查字段和 payload。
- AI 辅助抽取两份 PDF 中组件/API 封装、检测结果展示和 FormData 上传相关内容。
- AI 辅助补齐固定演示图、Recipe 生成链路、503/网络失败提示、测试和截图。
- 本人复核：
  - 确认 `confirmFoodIngredients()` 不上传 `candidate_id`、`confidence`、`bbox`。
  - 确认 `createRecipe()` 只传 `recognition_id` 和 `preferences`。
  - 确认没有修改 `backend/` 业务文件。
  - 确认没有修改 `frontend/src/router/index.js`、`AppSidebar.vue`、`ChatPage.vue`。
  - 确认没有提交 API Key、`.env`、`best.pt` 或大型数据集。

## 8. 对接、Commit 与 PR

- 本地提交信息计划：`feat(food): 接入食物识别 Mock 全链路`
- PR：未创建。
- Push：未执行，遵守“不要执行 Push、合并或权限设置”。
- 交付对象：吴雯验收 Mock E2E。

## 9. 风险和待对接

- 本地/远端目前未找到 `integration/day3-mock` 分支；`git fetch --all --prune` 时 Gitee `develop` 更新成功，但 GitHub 远端因本机代理 `127.0.0.1:7890` 不通拉取失败。
- 当前本地后端分支没有 `/api/food/recognitions` 和 `/api/recipes` V1 接口，因此本次页面手测使用前端 Mock 成功场景；页面默认仍保留“后端 Mock API”模式，待 `integration/day3-mock` 分支到位后可切换验证真实 HTTP。
- `bun run build` 有第三方依赖 annotation 和 chunk size warning，构建成功但可由后续统一性能优化处理。
