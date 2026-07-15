# Day 1：V1 契约与模块骨架

> 补录日期：2026-07-15。历史 Food 骨架提交：`fd870b7`。

## 完成内容

- 阅读并采用仓库根目录 `api_v1.md` 作为唯一对外接口标准。
- 建立 V1 Food DTO：`BoundingBox`、`ModelDetection`、`IngredientCandidate`、`ConfirmedIngredient`。
- 对外字段统一为 `candidate_id`、`class_name`、`display_name`、`ingredients`，不保留旧的 `key`、`name`、`confirmed_ingredients` 请求字段。
- 建立同步 `FoodRecognitionProvider` 接口，并提供可配置的 `MockFoodRecognitionProvider`。
- 建立 Food、Recipe、Chat Repository 文件和固定方法签名。

## 本人检查

- `IngredientCandidate.source` 仅允许 `model` / `manual`。
- 所有资源 ID 由 ORM 自增整数生成。
- Mock Provider 输出严格为 `list[ModelDetection]`，不写入数据库、不返回中文名。

## 结果与风险

- V1 DTO 契约测试通过，详见 Day 5 汇总。
- 真实模型权重不进入 Git；Day 1 仅完成 Provider 边界和 Mock 实现。
