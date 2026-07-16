# 食品 YOLO11 模型交付

本目录只负责 V1 食品识别模型。Food API 的多图上传、数据库、候选食材汇总和
`FoodRecognitionProvider` 适配由其他模块负责；模型始终只接收一张本地绝对路径图片。

## 固定接口

```python
recognize(image_path: str, conf_threshold: float = 0.25) -> list[ModelDetection]
```

每个检测结果必须含 `class_name`、`confidence` 和原图像素坐标 `bbox`；无结果返回
`[]`。模型不得接收图片数组、写数据库或生成 `candidate_id`。

## 环境与目录

使用服务器已有环境：

```bash
PY=/root/autodl-tmp/visagent/.venv-yolo/bin/python
ROOT=/root/autodl-tmp/visagent
cd "$ROOT/repository/backend/scripts/food_model"
```

已验证环境为 RTX 4090 48GB、CUDA、PyTorch 2.3.0+cu121、Ultralytics 8.4.96。
派生数据和报告保存在 `$ROOT/datasets`、`$ROOT/reports`；权重不进入 Git。最终只复制
冠军权重到仓库根目录 `models/food/best.pt`，供 Docker 挂载到 `/models/food/best.pt`。

## 本次交付版本与类别顺序

数据版本为 `$ROOT/datasets/fridge_original_v1`：3,148 张原始图片经 SHA-256 精确去重后
保留 3,049 张。以文件名 `_jpg.rf.` 之前的源 ID 分组，并以 `seed=42` 进行 80%/10%/10%
源图隔离划分；所有跨集合源图组和精确重复项均为 0。最终 12 类派生集为
`food12_grouped`（train/val/test 分别为 2,431/305/305 张）。

权重、`data.yaml` 和 `classes.yaml` 必须严格使用下列连续 ID；不得重排或改成复数名：

| ID | 模型名 | 中文展示名 |
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

## 执行顺序

### 1. 构建无泄漏 30 类基线数据

```bash
$PY prepare_dataset.py --mode prepare30
$PY validate_dataset.py --data "$ROOT/datasets/food30_grouped/data.yaml"
```

输出数据集为 `$ROOT/datasets/food30_grouped`，并生成：

- `$ROOT/reports/food/data/split_report.json`
- `$ROOT/reports/food/data/duplicate_issues.json`
- `$ROOT/reports/food/data/class_distribution.csv`
- `$ROOT/reports/food/data/audit_review.csv`

人工逐行审核 `audit_review.csv` 中每类 30 个独立源图框，将 `review_status` 改为
`pass` 或 `fail`。每类最多 1 个 `fail`，且不得保留 `pending`，才能进入最终 12 类筛选。
可先生成带红框的联系表以加快审核：

```bash
$PY render_audit_sheets.py --audit-file "$ROOT/reports/food/data/audit_review.csv" \
  --output-root "$ROOT/reports/food/data/audit_sheets"

# 审核者完成一个类别的 30 框复核后，逐行写入同一结论和可追溯备注
$PY record_audit.py --audit-file "$ROOT/reports/food/data/audit_review.csv" \
  --source-name tomato --status pass --note "reviewer/date"
```

### 2. YOLO11n 冒烟与 30 类基线

```bash
$PY train.py --data "$ROOT/datasets/food30_grouped/data.yaml" \
  --architecture yolo11n --epochs 1 --seed 42 --name food30_smoke_seed42 --smoke

$PY train.py --data "$ROOT/datasets/food30_grouped/data.yaml" \
  --architecture yolo11n --epochs 60 --seed 42 --name food30_baseline_seed42
```

### 3. 用严格审计和验证集指标选 12 类

```bash
$PY evaluate.py \
  --weights "$ROOT/reports/food/runs/food30_baseline_seed42/weights/best.pt" \
  --data "$ROOT/datasets/food30_grouped/data.yaml" --split val \
  --report-root "$ROOT/reports/food/baseline" --select-classes \
  --distribution-csv "$ROOT/reports/food/data/class_distribution.csv" \
  --audit-file "$ROOT/reports/food/data/audit_review.csv" \
  --selection-output "$ROOT/reports/food/baseline/selection.json"

$PY prepare_dataset.py --mode build12 \
  --output-root "$ROOT/datasets/food12_grouped" \
  --selection-file "$ROOT/reports/food/baseline/selection.json"
$PY validate_dataset.py --data "$ROOT/datasets/food12_grouped/data.yaml"
```

选择公式固定为 `0.50×AP50-95 + 0.25×Recall@0.25 + 0.15×源图覆盖度 + 0.10×AP50`。
严格审计、训练源图数不少于 60、验证源图数不少于 10 是进入排名的前置条件。类别 ID
会重新映射为连续的 `0–11`，并生成本目录下的 `classes.yaml`。

### 4. 最终 six-run 对比

对 `yolo11s`、`yolo11m` 分别执行 `seed=42,2026,3407`、100 epoch：

```bash
for arch in yolo11s yolo11m; do
  for seed in 42 2026 3407; do
    $PY train.py --data "$ROOT/datasets/food12_grouped/data.yaml" \
      --architecture "$arch" --epochs 100 --seed "$seed" \
      --name "food12_${arch}_seed${seed}"
  done
done
```

训练完成后用 results.csv 的最佳验证 mAP 和单图延迟确定架构；只有 YOLO11m 比
YOLO11s 高至少 `0.015` 且单图 P95 不超过 `50ms` 时才选择 m，否则选择 s：

```bash
$PY select_champion.py --data "$ROOT/datasets/food12_grouped/data.yaml" \
  --output "$ROOT/reports/food/final/champion.json"
```

随后仅对 `champion.json` 所指 run 在冻结测试集运行一次 `evaluate.py --split test`：

```bash
$PY evaluate.py \
  --weights "$ROOT/reports/food/runs/food12_yolo11s_seed3407/weights/best.pt" \
  --data "$ROOT/datasets/food12_grouped/data.yaml" --split test \
  --report-root "$ROOT/reports/food/final/test"
```

## 本次运行的证据与结果

- 30 类冒烟：`$ROOT/reports/food/runs/smoke_food30_yolo11n_seed42`。
- 30 类基线：`$ROOT/reports/food/runs/food30_baseline_yolo11n_seed42_rerun`，验证指标和 12 类
  排名见 `$ROOT/reports/food/baseline/metrics_val.json`、`selection.json`。
- 六次最终实验及曲线：`$ROOT/reports/food/runs/food12_yolo11s_seed{42,2026,3407}` 与
  `$ROOT/reports/food/runs/food12_yolo11m_seed{42,2026,3407}`。最终架构判定在
  `$ROOT/reports/food/final/champion.json`。
- 判定结果为 `yolo11s` seed 3407：s/m 三种子验证 mAP50-95 均值分别为 0.77901/0.78586；
  m 仅高 0.00684，未达到 0.015 门槛。s/m 单图 P95 分别为 10.15/10.35 ms。
- 唯一一次冻结测试集结果位于 `$ROOT/reports/food/final/test/metrics_test.json`：整体
  Precision 0.97498、Recall 0.85565、AP50 0.87362、AP50-95 0.62859，端到端单图 GPU
  P50/P95 为 8.14/8.43 ms。该目录同时含每类指标、混淆矩阵和固定图片推理结果。

## GPU 策略

脚本先探测 85% 显存可承载 batch，再限制为每 epoch 至少约 32 个优化步且为 8 的倍数。
数据以 RAM 缓存、16 workers、AMP 和单卡顺序训练运行；不要在同一张 GPU 上并行运行
多个 `train.py` 进程。

## 交付前验证与回滚

完成冠军测试集评估后，将 `best.pt` 复制至 `models/food/best.pt`，随后验证权重 metadata、
最终 data.yaml 和 classes.yaml 的 0–11 顺序完全相同：

```bash
$PY verify_delivery.py --weights "$ROOT/repository/models/food/best.pt" \
  --data "$ROOT/datasets/food12_grouped/data.yaml" --classes classes.yaml
```

`best.pt`、运行缓存、派生数据均被 Git 忽略。线上回滚只需将该文件恢复为前一版已验收
权重，并重新启动持有单例 Provider 的容器；不得改写 classes.yaml 的既有 ID 顺序。

## Docker 接线要求

后端负责人需保证：

1. 宿主机 `./models/food/best.pt` 挂载为 `/models/food/best.pt`；
2. `FOOD_CLASSES_PATH` 与 V1 一致，指向 `/app/backend/scripts/food_model/classes.yaml`；
3. backend 容器启用 NVIDIA GPU 透传；
4. Provider 只加载一次权重，逐张调用时复用同一实例，并以 `device=0`、`imgsz=640`、
   `half=True` 推理。

当前 Dockerfile 的实际应用目录与 V1 配置路径存在差异，必须由 Docker/后端负责人统一，
模型侧不修改其负责文件。

## V2：弱类数据补充与发布门槛

V1 冻结测试的 `beef` AP50-95 为 0.04661、`carrot` 为 0.31200；该测试集已暴露，
只能作为回归集，绝不能用于 V2 的类别选择、超参数选择或早停。V2 固定复用 V1 的
train/val 源图组，完全排除 V1 test，并只在冠军确认后分别评估新的 V2 test 和 V1 回归集。

补充数据必须放在 `$ROOT/datasets/food12_v2_supplement`，使用扁平 YOLO 目录：

```text
food12_v2_supplement/
  images/<独立拍摄源名>.jpg
  labels/<同名>.txt
```

每张补充图都必须至少包含 `beef` 或 `carrot` 的合法 0–11 标签。每类至少 150 个独立
拍摄源组；不得使用 V1 train/val 的精确重复图片。先运行预检，它会生成新增框的 100%
审核清单，并在数据不足时写出缺口但不会生成或改写 V2 数据集：

```bash
$PY prepare_v2_dataset.py --mode preflight
# 人工将 $ROOT/reports/food/v2/data/supplement_audit_100pct.csv 的每一行标为 pass
$PY prepare_v2_dataset.py --mode build \
  --audit-file "$ROOT/reports/food/v2/data/supplement_audit_100pct.csv" \
  --overwrite
$PY validate_dataset.py --data "$ROOT/datasets/food12_v2/data.yaml"
```

构建会拒绝：新增源图不足、未审核框、跨 V1 train/val 的精确重复、标签冲突，或最终
`beef`/`carrot` 未达到 train/val/test 分别 200/25/25 个独立源图组的情况。

V2 的六次训练和选型仍只使用验证集：

```bash
for arch in yolo11s yolo11m; do
  for seed in 42 2026 3407; do
    $PY train.py --data "$ROOT/datasets/food12_v2/data.yaml" \
      --architecture "$arch" --epochs 100 --seed "$seed" \
      --name "food12v2_${arch}_seed${seed}"
  done
done

$PY select_champion.py --run-prefix food12v2 \
  --data "$ROOT/datasets/food12_v2/data.yaml" \
  --output "$ROOT/reports/food/v2/final/champion.json"
```

冠军确定后，分别对 V2 test 和不参与选型的 V1 test 各运行一次评估，并执行质量门禁：

```bash
# 将 --weights 替换为 champion.json 中 chosen_run.weights；两次测试均不得早于冠军选定。
$PY evaluate.py --weights <冠军权重> --data "$ROOT/datasets/food12_v2/data.yaml" \
  --split test --report-root "$ROOT/reports/food/v2/final/v2_test"
$PY evaluate.py --weights <冠军权重> --data "$ROOT/datasets/food12_grouped/data.yaml" \
  --split test --report-root "$ROOT/reports/food/v2/final/v1_regression"
$PY check_v2_acceptance.py \
  --v2-metrics "$ROOT/reports/food/v2/final/v2_test/metrics_test.json" \
  --v1-regression-metrics "$ROOT/reports/food/v2/final/v1_regression/metrics_test.json" \
  --output "$ROOT/reports/food/v2/final/acceptance.json"
```

门禁为：V2 整体 AP50-95 不低于 0.65、每类 Recall@0.25 不低于 0.70、每类 AP50-95
不低于 0.50、P95 不超过 15 ms；V1 回归整体 AP50-95 不低于 0.62859，且 `beef`、
`carrot` AP50-95 不低于当前版本。未通过时必须回到补数和标注复核，不能依据测试结果
继续调参。

后端/Docker 的可合并接线说明见
`project_docs/integration/food_model_v2_backend_handoff.md`。它针对 Food Provider 所在的
`feature/backend-food-repository` 分支；当前模型分支不复制或重写 Food API、数据库、
Repository 与前端代码。
