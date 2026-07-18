# Food Model V1 制品说明

## 冻结选择

V1 演示模型固定为 **YOLO11s、seed 3407、输入 640、默认阈值 0.25**。YOLO11m 的平均
`mAP50-95` 只比 YOLO11s 高 `0.00684`，没有达到项目规定的 `0.015` 切换门槛，因此选择
更快的 YOLO11s。

冻结测试集报告的指标为：`mAP50-95=0.62859`、`Precision=0.97498`、
`Recall=0.85565`、单图 P50/P95 为 `8.14 / 8.43 ms`。这些是交付环境的测量值，不承诺在
不同 CPU、GPU、驱动或依赖版本上复现同样时延。

## 配对与完整性

| 文件 | 位置/名称 | 大小 | SHA-256 |
| --- | --- | ---: | --- |
| 权重 | `models/food/best.pt`（本地，忽略） | 19,194,771 bytes | `680accafc8c22854b37e959106c37a44b3e8c42b4d260d7f3c4681021c2a31cd` |
| 类别表 | `backend/scripts/food_model/classes.yaml`（跟踪） | 640 bytes | `8bd06c89afe18fbb6bf7d64d44b51f84f8199a80678e63123f35c09fd6c9913b` |

两者必须成对使用。类别索引从 0 开始，顺序固定为：`sugar`、`strawberry`、`beef`、
`chicken`、`cheese`、`milk`、`tomato`、`butter`、`corn`、`banana`、`egg`、`carrot`。
类别表使用 LF 结尾以便跨平台进行字节级校验。

## 下载与原生运行

从仓库根目录运行：

```powershell
.\scripts\download_food_model.ps1
```

脚本从 `food-model-v1.0` GitHub prerelease 下载附件到临时目录，校验发布校验和、
`best.pt`、`classes.yaml`，并拒绝覆盖不匹配的类别表。它只把通过校验的 `best.pt` 复制到
本地忽略目录 `models/food/best.pt`，不会读取或改写 `.env`。

原生后端使用项目锁定环境：

```powershell
cd backend
$env:FOOD_PROVIDER = 'yolo'
$env:FOOD_MODEL_PATH = "$PWD\..\models\food\best.pt"
$env:FOOD_CLASSES_PATH = "$PWD\scripts\food_model\classes.yaml"
$env:FOOD_CONF_THRESHOLD = '0.25'
$env:LLM_MODE = 'fake'
uv run uvicorn main:app --host 0.0.0.0 --port 8888
```

Docker 使用仓库根目录的只读挂载 `./models/food:/models/food:ro`；容器内设置
`FOOD_MODEL_PATH=/models/food/best.pt` 与
`FOOD_CLASSES_PATH=/app/backend/scripts/food_model/classes.yaml`。权重、数据集、训练缓存和
预测缓存均不得提交到 Git。

## 已知局限与发布要求

- 模型仅覆盖上述 12 类；未声明类别、遮挡、反光、低分辨率和域外食物可能漏检或误检。
- Food API 仍须遵守 V1.1：Provider 单图推理，Service 负责多图循环与 `image_index`。
- 用户必须确认候选食材；菜谱与营养数据不构成医学或营养建议。
- 当前项目锁定环境为 `ultralytics 8.4.98`、`torch 2.2.2+cpu`；交付验证环境为
  `ultralytics 8.4.96`、`torch 2.3.0+cu121`、CUDA 12.1。真实 GPU 发布验收应记录实际环境。
- 原始交付包包含训练机绝对路径元数据，不能直接作为公开 Release 附件。黄小石需提供不含
  私有路径、数据集或训练缓存的清理后发布包；发布包仍须保留同一 `best.pt` 与类别表哈希。
