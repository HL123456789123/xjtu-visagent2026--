# 食品模型 V2 后端与 Docker 接线单

## 适用范围

本接线单由模型分支交付，目标是 **`feature/backend-food-repository`** 中已经存在的
`YoloFoodRecognitionProvider`。不得在模型分支复制、替换或重做 Food API、数据库、
Repository、Service 的多图聚合逻辑。

公共接口保持冻结：

```python
recognize(image_path: str, conf_threshold: float = 0.25) -> list[ModelDetection]
```

Food Service 继续按上传顺序逐张调用；Provider 不接收图片数组，空结果必须为 `[]`。

## 必须修改

### 1. Provider 的确定性 GPU 推理与加载校验

目标文件：`backend/app/services/food_recognition_provider.py`。

`YoloFoodRecognitionProvider` 已有 `_model` 单例缓存，保留该行为；在第一次加载后新增
下列 fail-fast 校验：权重的 `model.names` 按 0..N-1 排序后，必须与 classes.yaml 中
`class_name` 的顺序完全相同，且类别数相同。任一不一致均抛出
`FoodModelUnavailableError`，不得静默按错误 ID 映射。

真实 `predict()` 调用固定传入：

```python
source=image_path, conf=conf_threshold, device=0, imgsz=640, half=True, verbose=False
```

保留原图 `box.xyxy` 像素坐标并构造 `ModelDetection`。启动或首次真实请求必须确认 CUDA
可用；CPU 回退不是生产降级路径，应返回模型不可用错误。

### 2. 镜像与 Compose

目标文件：`backend/Dockerfile`、`backend/pyproject.toml`、`docker-compose.yml`。

- 后端镜像改用与宿主驱动兼容的 CUDA 12.1 runtime；安装 Python 3.11、CUDA 版
  PyTorch 2.2.2+cu121、torchvision 0.17.2+cu121、Ultralytics 8.4.x。锁文件更新后必须
  使用 CUDA 索引安装，不能保留 PyPI 的 CPU-only torch。
- backend 服务配置 `gpus: all`，并设置 `NVIDIA_VISIBLE_DEVICES=all` 与
  `NVIDIA_DRIVER_CAPABILITIES=compute,utility`。
- 权重采用只读挂载：`./models/food:/models/food:ro`，环境变量
  `FOOD_MODEL_PATH=/models/food/best.pt`。
- 为严格遵守 V1，类别文件在容器内必须可读于
  `/app/backend/scripts/food_model/classes.yaml`。使用只读挂载
  `./backend/scripts/food_model:/app/backend/scripts/food_model:ro`，并设置
  `FOOD_CLASSES_PATH=/app/backend/scripts/food_model/classes.yaml`。
- 固定 `FOOD_PROVIDER=yolo`、`FOOD_CONF_THRESHOLD=0.25`；模型版本由发布版本号提供，
  不从用户输入读取。

## 联调验收

1. 下载仓库后先运行 `sha256sum models/food/best.pt`，其结果必须与
   `models/food/manifest.json` 的 `sha256` 一致；随后再构建容器。
2. 容器启动后执行 `python -c "import torch; assert torch.cuda.is_available()"`，并确认
   `torch.cuda.get_device_name(0)` 可返回 GPU 名称。
3. 校验 `/models/food/best.pt` 和 V1 classes 路径可读；故意替换错误 classes 文件时启动/
   首次加载必须失败，而不是输出错误类别。
4. 用单图、多食材图、空白图调用 Provider：字段仅为 V1 `ModelDetection` 所需的
   `class_name`、`confidence`、原图像素 `bbox`；空白图返回 `[]`；0.25 阈值生效。
5. 在同一进程连续处理 1 张和多张图片，替换并监视 `YOLO` 构造器，断言只加载一次模型，
   且 Food Service 以上传顺序聚合逐张结果。
6. 使用 V2 `acceptance.json` 为 `accepted: true` 的权重进行一轮真实容器推理，记录 GPU
   P50/P95，并将 `best.pt` 与 `classes.yaml` 作为不可拆分版本一同发布与回滚。

## 回滚

回滚只能成对恢复上一版已验收的 `models/food/best.pt` 和 `classes.yaml`，然后重建 backend
容器。不得仅替换权重、不得改写既有类别 ID，也不得为回滚改动冻结的 V1 接口。
