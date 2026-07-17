# 食品训练数据发布包

本目录使训练数据可获取、可审计，同时避免在 Git LFS 中重复存储同一批图片三次。所有
`*.tar.gz` 都由 Git LFS 管理；克隆后必须执行：

```bash
git lfs pull
sha256sum datasets/food/*.tar.gz
```

## 文件说明

| 文件 | 内容 | SHA-256 |
| --- | --- | --- |
| `fridge_original_v1.tar.gz` | 完整原始 Roboflow 30 类导出：图片、YOLO 标签、data.yaml 与原始 train/valid/test 目录。 | `4e53d1783256f7133fab5d67c53e406cdcd24bd51a7ac0760caca77e1e091de5` |
| `food30_grouped_metadata.tar.gz` | 无源图泄漏 30 类数据的标签、split、manifest、data.yaml 和元数据；图片由原始包加脚本重建。 | `794aecfead1426d538f7675112fc88988d97b2182413fd713c47aa4e8567491b` |
| `food12_grouped_metadata.tar.gz` | V1 最终 12 类数据的重映射标签、split、manifest、data.yaml 和元数据；图片由原始包加脚本重建。 | `f9ce458a607479a8fc670d8b1937f3d4df72101bad97c7bbd11952302fb440a8` |
| `food12_selection.json` | 30 类基线验证集产生的严格 12 类选择证据，供 `build12` 精确重建类别顺序。 | `bae7495d3fc9fd0ffa637ba2103643152a56d85113b696a850fec004df533710` |

原始包是唯一上传图片像素的完整训练集。30/12 类派生数据与其图片共享同一批源文件；若
将三个目录各自压缩会产生约 1.1 GB 的重复内容，因此只上传派生 split/标签元数据。该
设计不会损失可复现性。

## 重建训练集

解压原始包后，以仓库脚本重新生成派生数据：

```bash
ROOT=/root/autodl-tmp/visagent
tar -xzf datasets/food/fridge_original_v1.tar.gz -C "$ROOT/datasets"
PY="$ROOT/.venv-yolo/bin/python"
cd backend/scripts/food_model

$PY prepare_dataset.py --mode prepare30 --overwrite
# 12 类重建使用随仓库发布的严格选择证据。
$PY prepare_dataset.py --mode build12 \
  --selection-file "$ROOT/repository/datasets/food/food12_selection.json" --overwrite
```

实际训练前必须执行：

```bash
$PY validate_dataset.py --data "$ROOT/datasets/food30_grouped/data.yaml"
$PY validate_dataset.py --data "$ROOT/datasets/food12_grouped/data.yaml"
```

> 数据仅用于本项目训练、复现与展示。若需要对外分发，请先确认原始数据集的授权条件。
