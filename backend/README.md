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

---

## 业务模块设计

### 一、数据集管理

数据集作为系统一等公民进行管理，是模型训练的前置依赖。

#### 核心能力

- **数据集注册**：注册服务器上的数据集目录，自动解析 `data.yaml` 配置、统计图片数量和类别信息
- **目录浏览**：可视化浏览白名单目录（`ALLOWED_TRAINING_DIRS`），选择数据集路径和配置文件
- **自动发现**：递归扫描白名单目录，自动发现包含 `data.yaml`/`data.yml` 的未注册数据集，支持一键注册
- **数据集校验**：检查数据集完整性（目录是否存在、图片与标注数量匹配、YAML 格式正确）
- **训练关联**：训练任务创建时直接选择已注册的数据集，自动填充路径和 YAML 配置

#### 数据模型

```
Dataset
├── id, name, description
├── path              # 数据集根目录（服务器端绝对路径）
├── yaml_path         # data.yaml 路径
├── num_images        # 图片数量
├── num_classes       # 类别数
├── class_names       # 类别列表（JSON）
├── format            # 标注格式：yolo/voc/coco/labelme
└── status            # active / error
```

#### API 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/datasets/browse` | 浏览目录（白名单内） |
| GET | `/api/datasets/discover` | 自动发现未注册数据集 |
| POST | `/api/datasets/register` | 注册数据集 |
| GET | `/api/datasets` | 获取数据集列表（支持分页、状态筛选） |
| GET | `/api/datasets/{id}` | 获取数据集详情（含关联训练任务数） |
| DELETE | `/api/datasets/{id}` | 删除数据集（仅删除注册记录，有关联运行中任务时禁止删除） |
| POST | `/api/datasets/{id}/validate` | 校验数据集完整性 |

#### 路径白名单

数据集浏览、自动发现和训练路径校验均受白名单限制，在 `.env` 中配置：

```env
# 允许访问的目录白名单（逗号分隔，服务器端绝对路径）
ALLOWED_TRAINING_DIRS=/tmp,/data,/home
```

- 路径必须是**服务器端的绝对路径**
- Docker 部署时需配置**容器内路径**，并确保挂载了对应的宿主机目录

#### 权限配置

| 权限 | 说明 | 默认角色 |
|------|------|----------|
| `dataset:create` | 注册数据集 | admin, operator |
| `dataset:view` | 查看数据集 | 所有角色 |
| `dataset:manage` | 删除/校验数据集 | admin, operator |

---

### 二、模型训练

模型训练模块管理 YOLO 训练任务的全生命周期，训练完成后自动产出模型版本。

#### 核心能力

- **任务管理**：创建、启动、暂停、恢复、取消、删除训练任务
- **中断恢复**：基于 YOLO checkpoint 机制（`last.pt`），支持手动暂停/恢复和断电后自动续训
- **设备探测**：动态探测 CUDA GPU / Apple MPS / CPU，供用户选择训练设备
- **数据集关联**：创建任务时选择已注册的数据集，自动填充路径和 `data.yaml`
- **自动产出模型**：训练完成后自动将 `best.pt` 注册为 `ModelVersion`，版本号自动递增
- **逐 Epoch 指标记录**：通过 YOLO 回调机制，逐 epoch 记录 loss、mAP 等训练指标
- **任务状态恢复**：服务重启时自动处理中断任务——有 checkpoint 的标记为 paused，无 checkpoint 的标记为 failed

#### 任务状态流转

```
pending → running → completed
                ↘ paused → running（恢复）
                ↘ failed
                ↘ cancelled
```

- `pending`：任务已创建，等待启动
- `running`：训练进行中，可暂停或取消
- `paused`：已暂停，可恢复继续训练
- `completed`：训练正常完成
- `failed`：训练失败（异常或中断无 checkpoint）
- `cancelled`：用户主动取消

#### 数据模型

```
TrainingTask
├── id, user_id, model_id, task_uuid
├── status              # pending/running/paused/completed/failed/cancelled
├── base_architecture   # yolo26n/s/m/l/x
├── epochs, batch_size, img_size, device, optimizer, lr0
├── current_epoch, progress
├── checkpoint_path     # last.pt 路径（用于恢复）
├── dataset_id, dataset_path, data_yaml
├── set_as_default      # 训练完成后是否自动设为默认版本
└── error_message
```

#### 训练产出

训练完成后，`training_service._save_model_version()` 自动执行：
- 将 `best.pt` 注册为 `ModelVersion`
- 版本号自动递增：`v{count+1}.0.0`
- 根据 `set_as_default` 字段决定是否设为默认版本

#### API 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/training/devices` | 获取可用训练设备 |
| POST | `/api/training/tasks` | 创建训练任务 |
| GET | `/api/training/tasks` | 获取任务列表 |
| GET | `/api/training/tasks/{id}` | 获取任务详情 |
| GET | `/api/training/tasks/{id}/status` | 获取任务状态 |
| GET | `/api/training/tasks/{id}/metrics` | 获取训练指标 |
| POST | `/api/training/tasks/{id}/start` | 启动/恢复任务 |
| POST | `/api/training/tasks/{id}/pause` | 暂停任务 |
| POST | `/api/training/tasks/{id}/cancel` | 取消任务 |
| DELETE | `/api/training/tasks/{id}` | 删除任务 |

#### 权限配置

| 权限 | 说明 | 默认角色 |
|------|------|----------|
| `training:task:create` | 创建训练任务 | admin, operator |
| `training:task:manage` | 管理训练任务（启动/暂停/取消/删除） | admin, operator |
| `training:task:view` | 查看训练任务 | 所有角色 |

---

### 三、模型管理

模型管理模块采用 **Model + ModelVersion 两层架构**，Model 是逻辑实体，ModelVersion 是物理权重。

#### 核心能力

- **模型 CRUD**：创建、编辑、删除（软删除/归档）模型
- **版本管理**：训练自动产出、手动上传、ZIP 导入导出、设为默认版本
- **启用/禁用**：控制模型是否可被用于目标检测，只有已启用的模型才会出现在检测页面
- **场景关联**：将模型绑定到检测场景，支持设置场景默认模型

#### 两层架构设计

```
Model（逻辑实体）
├── 代表一类检测能力（如：遥感飞机检测）
├── 包含名称、基础架构、类别列表等元信息
├── status: active / archived（归档 = 软删除）
├── is_enabled: true / false（是否可被用于检测）
│
└── ModelVersion（物理版本）
    ├── 代表具体的 .pt 权重文件
    ├── 来源：training（训练产出）/ upload（手动上传）/ import（外部导入）
    ├── 包含版本号、mAP 指标、文件大小等
    └── is_default: 是否为该模型的默认版本
```

#### 数据模型

```
Model
├── id, name (unique), description
├── base_architecture   # yolo26n/s/m/l/x
├── category            # general/industrial/security/traffic/agriculture
├── class_names         # 类别列表（JSON）
├── class_names_cn      # 类别中文名映射（JSON）
├── status              # active / archived
├── is_enabled          # true / false（启用后才可用于检测）
└── created_by

ModelVersion
├── id, model_id (FK)
├── training_task_id (FK, nullable)
├── version             # 如 v1.0.0
├── source              # training / upload / import
├── model_path          # .pt 文件路径
├── map50, map50_95, precision, recall
├── file_size
├── is_default          # 是否为默认版本
└── status              # active / archived

SceneModel（场景-模型关联表）
├── scene_id (FK)
├── model_id (FK)
└── is_default          # 是否为该场景的默认模型
```

#### 启用/禁用机制

- 模型默认创建时为 `is_enabled = true`
- 只有 `status = active` 且 `is_enabled = true` 的模型才会出现在检测页面的模型下拉框中
- 禁用操作不影响模型本身的数据，仅阻止其被用于检测

#### API 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/models` | 获取模型列表（支持分类/状态筛选） |
| POST | `/api/models` | 创建模型 |
| GET | `/api/models/{id}` | 获取模型详情（含版本列表和关联场景） |
| PUT | `/api/models/{id}` | 更新模型信息 |
| PUT | `/api/models/{id}/toggle` | 切换模型启用/禁用状态 |
| DELETE | `/api/models/{id}` | 归档模型（软删除） |
| GET | `/api/models/{id}/versions` | 获取版本列表 |
| PUT | `/api/models/{id}/versions/{vid}/default` | 设为默认版本 |
| DELETE | `/api/models/{id}/versions/{vid}` | 归档版本 |
| GET | `/api/models/{id}/versions/{vid}/export` | 导出模型 ZIP 包 |
| POST | `/api/models/{id}/import` | 从 ZIP 导入模型版本 |
| GET | `/api/models/scenes/{sceneId}/models` | 获取场景关联的已启用模型 |
| POST | `/api/models/scenes/{sceneId}/bindmodel` | 绑定模型到场景 |
| DELETE | `/api/models/scenes/{sceneId}/bindmodel/{modelId}` | 解绑模型与场景 |

#### ZIP 导入导出格式

```
model_name_version.zip
├── manifest.json      # 元信息（模型名、版本、架构、指标等）
├── weights/best.pt    # 权重文件
└── config/model.json  # 模型配置（架构、类别信息）
```

---

### 四、目标检测

目标检测模块基于场景+模型进行推理，支持单图、批量、视频和实时摄像头四种检测模式。

#### 核心能力

- **场景驱动**：检测以场景为上下文，每个场景定义检测类别体系
- **模型绑定**：场景通过 `SceneModel` 关联已启用的模型，检测时从场景关联的模型中选择
- **多模式检测**：单图检测、批量检测、视频检测、实时摄像头（WebSocket + 抽帧）
- **默认模型**：场景可设置默认模型，选择场景后自动选中

#### 检测流程

```
1. 用户选择检测场景
2. 系统加载该场景关联的已启用模型（通过 SceneModel 表）
3. 自动选中场景默认模型（如有）
4. 用户选择检测模型、检测模式、参数（置信度/IoU 阈值）
5. 上传文件或开启摄像头
6. 后端使用选中模型的默认版本执行推理
7. 返回检测结果（检测框、类别、置信度）
```

#### 场景与模型的绑定关系

- 一个场景可关联多个模型（N:M 关系）
- 只有 `status = active` 且 `is_enabled = true` 的模型才会出现在检测页面的模型下拉框中
- 每个场景可设置一个默认模型（`SceneModel.is_default = true`）
- 检测接口通过 `model_version_id` 指定具体使用的模型版本（前端自动取选中模型的默认版本 ID）

#### 数据模型

```
DetectionScene（检测场景）
├── id, name, display_name, description
├── category            # 场景分类
├── class_names         # 检测类别列表（JSON）
└── is_active

DetectionTask（检测任务）
├── id, user_id, scene_id, model_version_id
├── task_type           # single/batch/video/camera
├── status, total_images, total_objects
├── conf_threshold, iou_threshold, image_size
└── error_message, analysis_report

DetectionResult（检测结果）
├── id, task_id
├── class_name, class_id, confidence
├── bbox                # [x1, y1, x2, y2]
└── inference_time
```

#### API 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/detection/scenes` | 获取检测场景列表 |
| POST | `/api/detection/scenes` | 创建检测场景 |
| POST | `/api/detection/single` | 单图检测 |
| POST | `/api/detection/batch` | 批量检测 |
| POST | `/api/detection/video` | 视频检测 |
| GET | `/api/detection/tasks` | 获取检测任务列表 |
| GET | `/api/detection/tasks/{id}` | 获取检测任务详情 |
| GET | `/api/detection/tasks/{id}/results` | 获取检测结果 |

#### 摄像头实时检测

摄像头模式通过 WebSocket 实现实时检测：
- 前端通过 `getUserMedia` 获取摄像头画面
- 定时抽帧转为 JPEG 通过 WebSocket 发送到后端
- 后端执行推理后将检测结果返回前端
- 前端在 Canvas 上绘制检测框并实时更新

---

## 模块间数据流转

```
数据集管理 ──(选择数据集)──→ 模型训练 ──(自动产出 ModelVersion)──→ 模型管理
                                                                    │
                                                          绑定到场景 │
                                                                    ↓
                                              目标检测 ←── 选择场景 + 选择模型
```

1. **数据集 → 训练**：训练任务创建时选择已注册的数据集，自动填充路径和 YAML 配置
2. **训练 → 模型**：训练完成后自动将 `best.pt` 注册为 `ModelVersion`
3. **模型 → 检测**：模型启用后，通过 `SceneModel` 绑定到场景，检测时从场景关联的已启用模型中选择

---

## 训练模块 API（补充）

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
