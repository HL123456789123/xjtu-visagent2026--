# 食品识别模型交付总览

> 适用对象：模型训练、Food Service、后端/Docker 和联调负责人。
> 当前代码分支：`feature/model-food-yolo`；交付 PR：#5（目标 `develop`）。

## 1. 当前已经交付什么

项目已从通用 YOLO 检测平台中独立出食品识别模型侧能力，模型侧只负责单张本地图片
的检测；多图上传、按顺序聚合、候选食材、数据库和菜谱/营养流程仍由 Food Service
负责。

固定模型接口为：

```python
recognize(image_path: str, conf_threshold: float = 0.25) -> list[ModelDetection]
```

每个结果只包含 `class_name`、`confidence` 和原图像素坐标 `bbox`；没有检测结果时返回
`[]`。模型不能接收图片数组，也不能写数据库或生成 `candidate_id`。

V1 冠军权重位于仓库 `models/food/best.pt`，会随 GitHub 分支发布；类别映射位于
`backend/scripts/food_model/classes.yaml`。`models/food/manifest.json` 固化 SHA-256、文件
大小、架构与类别顺序。权重、数据集 `data.yaml` 与类别文件已经过 ID 顺序一致性校验。

## 2. V1 模型与数据结论

V1 从 30 类数据中通过无源图泄漏的验证集选出以下 12 类，ID 必须永久保持不变：

| ID | class_name | 中文名 |
| --- | --- | --- |
| 0 | sugar | 糖 |
| 1 | strawberry | 草莓 |
| 2 | beef | 牛肉 |
| 3 | chicken | 鸡肉 |
| 4 | cheese | 奶酪 |
| 5 | milk | 牛奶 |
| 6 | tomato | 番茄 |
| 7 | butter | 黄油 |
| 8 | corn | 玉米 |
| 9 | banana | 香蕉 |
| 10 | egg | 鸡蛋 |
| 11 | carrot | 胡萝卜 |

训练对比了 YOLO11s、YOLO11m 各 3 个 seed。m 的验证集均值仅比 s 高 0.00684，未满足
0.015 的替换门槛，因此选择 YOLO11s（seed 3407）。V1 冻结测试集指标：

- Precision `0.97498`、Recall `0.85565`、AP50 `0.87362`、AP50-95 `0.62859`
- RTX 4090 单图端到端 GPU P50/P95：`8.14 / 8.43 ms`
- 主要风险：`beef` AP50-95 为 `0.04661`，`carrot` 为 `0.31200`；它们不能作为业务稳定类别承诺。

数据、训练和报告均位于 `/root/autodl-tmp/visagent`，避免根分区占满。V1 测试集现已
见过结果，只能作为未来版本的回归集，不能再用于模型选择或调参。

## 3. V2 当前状态与启动条件

V2 的脚本已经具备，但尚未产生 V2 数据集、权重或发布结论。原因是当前没有可用的真实
新增图片和标注。预检结果为：`beef` 缺 150 个独立拍摄源组，`carrot` 缺 150 个独立
拍摄源组。

新增数据放入：

```text
/root/autodl-tmp/visagent/datasets/food12_v2_supplement/
  images/<独立拍摄源名>.jpg
  labels/<同名>.txt
```

要求：每张补充图至少有一个 beef/carrot 标签；新增框必须 100% 人工审核为 `pass`；
不能与 V1 train/val 存在 SHA-256 精确重复。V2 构建器会将 V1 train/val 和补充数据按
源图组重新划分为 80%/10%/10%，彻底排除 V1 test。

V2 发布门槛：整体 AP50-95 ≥ 0.65、每类 Recall@0.25 ≥ 0.70、每类 AP50-95 ≥ 0.50、
P95 ≤ 15 ms；并且在 V1 回归集上不得低于当前整体指标，beef/carrot 也不得倒退。

具体命令、审核流程和六次训练流程见
[模型 README](../../backend/scripts/food_model/README.md)。

## 4. 后端与 Docker 接线

Food Provider 必须只加载一次 `best.pt`，随后逐张复用同一模型实例。真实推理固定使用
`device=0`、`imgsz=640`、`half=True`，并在首次加载时校验权重 `model.names` 与
`classes.yaml` 的类别数、ID 和名称完全一致；不一致时应以模型不可用失败，不能返回错类。

容器要求：

```text
宿主 ./models/food/best.pt
  -> 容器 /models/food/best.pt

宿主 ./backend/scripts/food_model/classes.yaml
  -> 容器 /app/backend/scripts/food_model/classes.yaml
```

环境变量必须设为：

```text
FOOD_PROVIDER=yolo
FOOD_MODEL_PATH=/models/food/best.pt
FOOD_CLASSES_PATH=/app/backend/scripts/food_model/classes.yaml
FOOD_CONF_THRESHOLD=0.25
```

镜像必须使用 CUDA 运行时和 CUDA 版 PyTorch；Compose 必须启用 `gpus: all`、
`NVIDIA_VISIBLE_DEVICES=all`、`NVIDIA_DRIVER_CAPABILITIES=compute,utility`。完整可合并
修改点及容器验收步骤见
[后端接线单](food_model_v2_backend_handoff.md)。该代码位于协作方
`feature/backend-food-repository` 分支，模型分支不复制 Food API 或数据库实现。

## 5. 发布、验收与回滚

1. 模型负责人交付配套的 `best.pt` 和 `classes.yaml`；二者不可拆分替换。
2. 后端负责人按接线单构建 GPU 容器，确认 CUDA 可用、两个文件可读、类别校验通过。
3. 联调单图、多食材图、空白图，并确认多图服务逐张调用时不重复加载模型。
4. V2 只有在逐类门禁生成 `accepted: true` 后才能替换 `models/food/best.pt`。
5. 回滚时成对恢复上一版已验收的权重和类别文件，重建 backend 容器；不得调整类别 ID。

## 6. 关键文件索引

- [训练/评估/数据脚本与命令](../../backend/scripts/food_model/README.md)
- [V1 类别定义](../../backend/scripts/food_model/classes.yaml)
- [V2 后端与 Docker 接线单](food_model_v2_backend_handoff.md)
- 外部报告根目录：`/root/autodl-tmp/visagent/reports/food`
- V1 交付权重：`models/food/best.pt`（随 GitHub 发布）
- 权重校验清单：`models/food/manifest.json`
