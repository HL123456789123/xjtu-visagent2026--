# 食品模型展示材料

本目录是 GitHub 可直接预览的小体积展示包，不含训练 checkpoint 或完整数据图片。

- `audit_sheets/`：30 个类别的标注联系表，每张图抽取 30 个独立源图框，适合检查类别与
  标注质量。
- `data_summary/`：数据去重、源图分割、人工审核、30 类基线指标和最终 12 类选择证据。
- `final_test/`：V1 冠军模型的冻结测试指标、混淆矩阵、PR/F1/P/R 曲线、预测示例和空图
  结果；`blank.png` 应对应空检测结果。

完整训练图片请使用 [`datasets/food`](../../datasets/food/README.md) 的 Git LFS 发布包。
最终部署权重、类别映射和推理参数见 [`models/food`](../../models/food/manifest.json)。
