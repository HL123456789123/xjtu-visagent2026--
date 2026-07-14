# 接线需求记录

## CR-FE-FOOD-001：食物工作流页面 router/sidebar 接线

- 日期：2026-07-14
- 提交人：刘楚涵
- 共享文件 owner：闫灿宇或当天指定前端集成人
- 状态：已接线
- 本次接线：已修改 `frontend/src/router/index.js` 和 `frontend/src/components/layout/AppSidebar.vue`

### 目标文件

- `frontend/src/router/index.js`
- `frontend/src/components/layout/AppSidebar.vue`

### 建议变更

1. 在 MainLayout 子路由中增加食物工作流页面：

```js
{
  path: 'food-recipes',
  name: 'FoodRecipe',
  component: () => import('@/views/FoodRecipePage.vue'),
  meta: { title: '食物菜谱', icon: 'Dish', permission: 'food:recognition:create' },
}
```

2. 在侧边栏普通菜单中增加入口：

```js
{ path: '/food-recipes', title: '食物菜谱', icon: Dish, permission: 'food:recognition:create' }
```

3. 当前 Day1 演示阶段暂不加 `permission`，保证普通测试用户可以打开页面；正式权限后续建议与后端食物识别创建/查看权限对齐。

### 实际接线结果

- `/` 默认重定向到 `/food-recipes`，避免无旧菜单权限的测试用户进入 `/chat` 后看到 404。
- 新增 `/food-recipes` 路由，渲染 `FoodRecipePage.vue`。
- 侧边栏新增“食物菜谱”入口，暂不绑定旧权限。

### 变更原因

- `FoodRecipePage.vue` 已完成无后端 Mock 的上传、预览、识别状态、食材编辑和确认骨架。
- 页面向菜谱展示区域输出的契约已经固定为：
  - props：`recognitionId`、`confirmedIngredients`、`status`、`provider`、`modelVersion`
  - emits：`generate-recipe`
  - 事件 payload：`{ recognition_id, confirmed_ingredients }`
- 需要共享 owner 统一接线，避免多人同时修改 router/sidebar。

### 验证方式

- 打开 `/food-recipes`，默认应显示 `idle` 页面状态。
- 选择 JPG/PNG 后进入 `selecting`，点击识别后可用 Mock 成功进入 `recognized`。
- 确认食材后进入 `confirmed`，`RecognitionSummary` 显示 `recognition_id` 和 `confirmed_ingredients` 数量，点击“生成菜谱”触发 `generate-recipe`。
- 运行 `bun run test`，当前结果为 6 个测试文件、40 个用例通过。

### 期望接线日期

- 2026-07-14 Day1 晚间统一共享文件接线窗口。
