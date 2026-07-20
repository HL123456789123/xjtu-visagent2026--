# 前端质量 RC 升级与验证记录

## 基线与备份

- 开发分支：`codex/frontend-quality-rc`
- 功能检查点：`35a4bd8 feat(food): 完善菜谱版本交互与多图体验`
- 修改前基线：`23302557162d996cd5732b0879f524fde64ebd8f`
- 本地备份：`D:\bytecreek\backups\visagent\20260720-163022-pre-frontend-upgrade`
- 备份包含 Git bundle、工作区 patch、PostgreSQL 自定义格式逻辑备份和 SHA-256 清单。
- `git bundle verify` 通过；`pg_restore --list` 可读取 406 项。

## 本轮变更

- 增加 ESLint flat config，以及只检查的 `bun run lint` 和显式修复的 `bun run lint:fix`。
- 合并普通请求与上传请求的响应错误处理，保持两个 Axios 客户端的公开导出和超时配置不变。
- 将 Food 顶部流程状态、菜谱工作区和菜谱状态逻辑从 `FoodRecipePage.vue` 分离。
- `FoodRecipePage.vue` 从约 900 行降低至 379 行；上传器、食材编辑器和既有接口契约未改变。
- 新增流程头部、菜谱工作区和请求拦截器测试。

## 自动化结果

从 `frontend/` 实际执行：

```text
bun run lint   通过
bun run test   22 个测试文件、154 项测试通过
bun run build  通过
```

构建体积对比：

| 资源 | 修改前 | 修改后 | 结果 |
| --- | ---: | ---: | --- |
| 主入口 JS | 1,060.20 kB / gzip 346.70 kB | 1,059.61 kB / gzip 346.69 kB | 无回归 |
| Food 页面 JS | 26.15 kB / gzip 9.19 kB | 28.88 kB / gzip 9.88 kB | 增长低于 5% 总入口阈值 |
| Dashboard JS | 1,123.26 kB / gzip 373.36 kB | 1,123.26 kB / gzip 373.36 kB | 未改动 |

构建仍会报告 VueUse pure annotation 和超过 500 kB chunk 的既有警告。本轮不进行 Element Plus 按需导入或 ECharts 拆包。

## Docker 与页面复验

- `docker compose -p visagent-history-dev config -q` 通过。
- frontend 镜像生产构建通过，Nginx 阶段复制完成。
- 五个服务运行；backend 健康检查返回 200，frontend 返回 200。
- 运行模式最终确认：`FOOD_PROVIDER=yolo`、`LLM_MODE=real`，未记录任何 Key 或环境文件内容。
- 浏览器验证：首页、普通用户导航、单图、8 图和 9 图拒绝均正常。
- 真实 YOLO 完成识别，真实 LLM 生成 v1；Chat 修改生成 v2。
- 标题版本选择器可查看 v1 并返回当前 v2；分享弹窗固定在当前视口。
- 历史页和个人看板显示真实个人数据；刷新及 backend/frontend 重启后 v2 与两条 Chat 消息仍可恢复。
- 验证使用的随机临时账号、关联数据库记录、MinIO 对象和本地测试图片已删除。

## 新发现与后续

- 首个新问题：执行 `docker compose up -d --force-recreate frontend` 时，Compose 同时重建了 frontend 的 backend 依赖，导致未显式传入的 `FOOD_PROVIDER` 回落为 `mock`。本轮已用 `--no-deps` 单独恢复 backend 为 `yolo + real` 并复验健康。后续只更新前端时应优先使用 `docker compose up -d --no-deps --force-recreate frontend`。
- Vitest 仍会输出部分 Element Plus 组件未注册警告，但测试全部通过；后续可在统一测试 setup 中注册轻量 stub。
- Element Plus 按需加载、ECharts 拆包、TypeScript、Playwright 独立环境、国际化和 CDN 继续留在答辩后的第二阶段。
- 本记录不代表最终发布通过。
