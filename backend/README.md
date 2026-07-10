# VisAgent 后端

## 默认测试账号

系统启动时会自动创建以下默认用户，密码规则为：**用户名首字母大写 + @2026**

| 用户名 | 密码 | 邮箱 | 角色 |
|--------|------|------|------|
| super | Super@2026 | super@visagent.com | 超级管理员 |
| admin | Admin@2026 | admin@visagent.com | 管理员 |
| operator | Operator@2026 | operator@visagent.com | 操作员 |
| user | User@2026 | user@visagent.com | 普通用户 |
| viewer | Viewer@2026 | viewer@visagent.com | 访客 |

## 训练模块 API

### 设备探测

`GET /api/training/devices`

动态探测当前服务器可用的训练设备，返回设备列表供前端选择。

**响应示例：**

```json
{
  "code": 200,
  "data": [
    {"value": "cpu", "label": "CPU", "description": "使用处理器训练"},
    {"value": "0", "label": "GPU 0", "description": "NVIDIA GeForce RTX 4090"},
    {"value": "mps", "label": "MPS", "description": "Apple Silicon GPU 加速"}
  ]
}
```

**探测逻辑：**

- 始终包含 `cpu` 选项
- 通过 `torch.cuda.is_available()` 检测 CUDA GPU，列出所有可用显卡
- 通过 `torch.backends.mps.is_available()` 检测 Apple Silicon MPS 加速

### 任务管理

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/training/tasks` | 创建训练任务 |
| GET | `/api/training/tasks` | 获取任务列表 |
| GET | `/api/training/tasks/{id}` | 获取任务详情 |
| POST | `/api/training/tasks/{id}/start` | 启动任务 |
| POST | `/api/training/tasks/{id}/pause` | 暂停任务 |
| POST | `/api/training/tasks/{id}/cancel` | 取消任务 |
| DELETE | `/api/training/tasks/{id}` | 删除任务 |
| GET | `/api/training/tasks/{id}/metrics` | 获取训练指标 |
