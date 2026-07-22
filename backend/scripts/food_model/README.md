# 食物识别模型脚本与运行时

本目录保留黄小石分支中可复用的类别表、数据准备、训练、评估和数据校验脚本。
应用运行时位于 `backend/app/modeling/food_yolo_runtime.py`。

## V1.1 边界

- Provider 只接收一个本地绝对图片路径和 `conf_threshold`。
- 返回 `list[ModelDetection]`；每项只有 `class_name`、`confidence` 和
  `bbox{x1,y1,x2,y2}`。
- 无检测结果返回空列表。
- Provider 不接收图片数组，不生成 `image_index` 或数据库 ID，也不访问数据库。
- 多图循环、聚合、原子失败和 `image_index` 由 Food Service 负责。

## 类别与权重

类别顺序以 `classes.yaml` 为准。模型权重、完整数据集、`runs/`、训练缓存、审计图片和
生成报告均不得进入 Git。部署时通过 `FOOD_MODEL_PATH` 指向宿主机挂载的已验收权重，
通过 `FOOD_CLASSES_PATH` 指向本目录的 `classes.yaml`。

## 脚本

脚本在 `backend/` 的项目环境中运行，依赖安装和具体命令必须遵守仓库根目录
`AGENTS.md`。训练数据和输出目录必须位于仓库之外。

- `prepare_dataset.py`：按源图分组构建无泄漏数据集。
- `validate_dataset.py`：校验图片、标签和跨集合重复。
- `train.py`：运行 YOLO 训练。
- `evaluate.py`：评估模型并输出指标。
- `catalog.py`：维护原始类别到稳定输出类别的映射。

本集成只验证脚本语法和 Provider 的隔离测试；没有在本机运行 GPU 训练或真实权重推理。
