# Day 4：真实 YOLO Provider 与不可用处理

> 补录日期：2026-07-15。

## 完成内容

- 实现 `YoloFoodRecognitionProvider`：读取 `FOOD_MODEL_PATH`、`FOOD_CLASSES_PATH`、`FOOD_MODEL_VERSION`。
- 新增 `backend/scripts/food_model/classes.yaml`，提供 `class_name` 到 `display_name` 映射。
- 使用 Ultralytics YOLO 推理，将 `xyxy`、置信度、类别转换为 V1 `ModelDetection`。
- 模型权重、类别文件、模型加载或推理不可用时，Food API 返回 HTTP 503，消息为“食物识别模型暂不可用”。
- Docker Compose 已声明只读权重挂载：`./models/food:/models/food:ro`。

## 本人检查

- 缺失权重的 Provider 单测已验证抛出 `FoodModelUnavailableError`。
- Food API 测试已验证该错误映射为 503，并验证不会自动从 yolo 降级为 mock。

## 未完成的外部验证

- 本仓库未提供 `models/food/best.pt`，无法对固定图执行真实推理。
- Docker daemon 当前未启动，无法在容器中验证权重挂载和运行日志。
