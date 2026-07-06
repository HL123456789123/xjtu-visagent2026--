"""
训练模块 API 路由
提供训练任务管理、数据集上传验证等接口
"""

import os
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Request
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.config.settings import settings
from app.core.security import get_current_user, RequirePermission
from app.core.logger import get_logger
from app.core.tz import now_cst
from app.database.session import get_db
from app.entity.db_models import User, Model, ModelVersion, TrainingTask
from app.entity.schemas import ApiResponse
from app.core.rate_limiter import limiter
from app.services.training_service import training_service
from app.services.data_utils import (
    validate_dataset,
    split_dataset,
    generate_data_yaml,
    convert_voc_to_yolo,
    convert_coco_to_yolo,
    convert_labelme_to_yolo,
)

logger = get_logger("training_api")

router = APIRouter(prefix="/api/training", tags=["训练管理"])


def _validate_training_path(file_path: str, label: str = "路径"):
    """校验训练相关路径是否在白名单目录内"""
    resolved = Path(file_path).resolve()
    allowed_dirs = [d.strip() for d in settings.ALLOWED_TRAINING_DIRS.split(",") if d.strip()]
    for allowed in allowed_dirs:
        try:
            resolved.relative_to(Path(allowed).resolve())
            return  # 路径在白名单内
        except ValueError:
            continue
    raise HTTPException(
        status_code=400,
        detail=f"{label}不在允许的目录内，允许的目录: {', '.join(allowed_dirs)}",
    )


def _get_task_or_403(db: Session, task_id: int, user: User):
    """获取训练任务并校验所有权，超级管理员可管理所有任务"""
    task = db.query(TrainingTask).filter(TrainingTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="训练任务不存在")
    # 超级管理员直接放行
    if user.is_superuser:
        return task
    if task.user_id != user.id:
        raise HTTPException(status_code=403, detail="无权操作该训练任务")
    return task


@router.post("/tasks", response_model=ApiResponse, dependencies=[Depends(RequirePermission("training:task:create"))])
@limiter.limit("10/minute")
async def create_training_task(
    request: Request,
    model_id: int = Form(..., description="模型ID"),
    base_architecture: str = Form("yolov11n", description="基础架构：yolov11n/s/m/l/x"),
    epochs: int = Form(100, ge=1, le=1000, description="训练轮数"),
    img_size: int = Form(640, ge=320, le=2048, description="图像尺寸"),
    batch_size: int = Form(16, ge=1, le=256, description="批次大小"),
    device: str = Form("cpu", description="训练设备：0/1/cpu"),
    optimizer: str = Form("SGD", description="优化器：SGD/Adam/AdamW"),
    lr0: float = Form(0.01, ge=0.0001, le=0.1, description="初始学习率"),
    dataset_path: str = Form(..., description="数据集路径"),
    data_yaml: str = Form(..., description="data.yaml 路径"),
    set_as_default: bool = Form(False, description="训练完成后是否自动设为默认版本"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """创建训练任务"""
    # 验证模型是否存在
    model_obj = db.query(Model).filter(Model.id == model_id).first()
    if not model_obj:
        raise HTTPException(status_code=404, detail="模型不存在")

    # 校验路径安全性
    _validate_training_path(dataset_path, "数据集路径")
    _validate_training_path(data_yaml, "data.yaml 路径")

    config = {
        "base_architecture": base_architecture,
        "epochs": epochs,
        "img_size": img_size,
        "batch_size": batch_size,
        "device": device,
        "optimizer": optimizer,
        "lr0": lr0,
        "dataset_path": dataset_path,
        "data_yaml": data_yaml,
        "set_as_default": set_as_default,
    }

    task = training_service.create_training_task(
        db=db, user_id=current_user.id, model_id=model_id, config=config
    )

    return ApiResponse(
        code=200,
        message="训练任务创建成功",
        data={"task_id": task.id, "task_uuid": task.task_uuid, "status": task.status},
    )


@router.post("/tasks/{task_id}/start", response_model=ApiResponse, dependencies=[Depends(RequirePermission("training:task:manage"))])
async def start_training(
    task_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    """启动训练任务"""
    _get_task_or_403(db, task_id, current_user)  # 校验所有权
    success = training_service.start_training(db, task_id)
    if not success:
        raise HTTPException(status_code=400, detail="启动训练失败")

    return ApiResponse(code=200, message="训练任务已启动")


@router.post("/tasks/{task_id}/pause", response_model=ApiResponse, dependencies=[Depends(RequirePermission("training:task:manage"))])
async def pause_training(
    task_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    """暂停训练任务"""
    _get_task_or_403(db, task_id, current_user)  # 校验所有权
    success = training_service.pause_training(db, task_id)
    if not success:
        raise HTTPException(status_code=400, detail="暂停训练失败")

    return ApiResponse(code=200, message="训练任务已暂停")


@router.post("/tasks/{task_id}/cancel", response_model=ApiResponse, dependencies=[Depends(RequirePermission("training:task:manage"))])
async def cancel_training(
    task_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    """取消训练任务"""
    _get_task_or_403(db, task_id, current_user)  # 校验所有权
    success = training_service.cancel_training(db, task_id)
    if not success:
        raise HTTPException(status_code=400, detail="取消训练失败")

    return ApiResponse(code=200, message="训练任务已取消")


@router.get("/tasks/{task_id}", response_model=ApiResponse, dependencies=[Depends(RequirePermission("training:task:view"))])
async def get_training_task(
    task_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    """获取训练任务详情"""
    _get_task_or_403(db, task_id, current_user)  # 校验所有权
    status = training_service.get_training_status(db, task_id)
    if not status:
        raise HTTPException(status_code=404, detail="训练任务不存在")

    return ApiResponse(code=200, data=status)


@router.get("/tasks/{task_id}/status", response_model=ApiResponse, dependencies=[Depends(RequirePermission("training:task:view"))])
async def get_training_status(
    task_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    """获取训练状态"""
    _get_task_or_403(db, task_id, current_user)  # 校验所有权
    status = training_service.get_training_status(db, task_id)
    if not status:
        raise HTTPException(status_code=404, detail="训练任务不存在")

    return ApiResponse(code=200, data=status)


@router.get("/tasks/{task_id}/metrics", response_model=ApiResponse, dependencies=[Depends(RequirePermission("training:task:view"))])
async def get_training_metrics(
    task_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    """获取训练指标"""
    _get_task_or_403(db, task_id, current_user)  # 校验所有权
    metrics = training_service.get_training_metrics(db, task_id)
    return ApiResponse(code=200, data=metrics)


@router.post("/tasks/{task_id}/validate", response_model=ApiResponse, dependencies=[Depends(RequirePermission("training:task:manage"))])
async def validate_model(
    task_id: int,
    data_yaml: Optional[str] = Form(None, description="数据集配置文件路径（可选）"),
    img_size: int = Form(640, description="图像尺寸"),
    batch_size: int = Form(16, description="批次大小"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """模型评估

    对训练完成的模型在验证集上进行评估，返回 mAP、precision、recall 等指标
    """
    _get_task_or_403(db, task_id, current_user)  # 校验所有权
    result = training_service.validate_model(
        db=db, task_id=task_id, data_yaml=data_yaml, img_size=img_size, batch_size=batch_size
    )

    if not result:
        raise HTTPException(status_code=400, detail="模型评估失败，请检查任务状态和模型文件")

    return ApiResponse(code=200, message="模型评估完成", data=result)


@router.get("/tasks", response_model=ApiResponse, dependencies=[Depends(RequirePermission("training:task:view"))])
async def get_training_tasks(
    model_id: Optional[int] = None,
    status: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取训练任务列表"""
    result = training_service.get_task_list(
        db=db,
        user_id=current_user.id,
        model_id=model_id,
        status=status,
        page=page,
        page_size=page_size,
    )

    return ApiResponse(code=200, data=result)


@router.post("/datasets/validate", response_model=ApiResponse, dependencies=[Depends(RequirePermission("training:task:create"))])
async def validate_dataset_api(
    images_dir: str = Form(..., description="图像目录路径"),
    labels_dir: str = Form(..., description="标注目录路径"),
    class_names: str = Form(..., description="类别名称，逗号分隔"),
    current_user: User = Depends(get_current_user),
):
    """验证数据集"""
    class_list = [name.strip() for name in class_names.split(",")]
    result = validate_dataset(images_dir, labels_dir, class_list)

    return ApiResponse(code=200, message="数据集验证完成", data=result)


@router.post("/datasets/split", response_model=ApiResponse, dependencies=[Depends(RequirePermission("training:task:create"))])
async def split_dataset_api(
    images_dir: str = Form(..., description="图像目录路径"),
    labels_dir: str = Form(..., description="标注目录路径"),
    output_dir: str = Form(..., description="输出目录路径"),
    train_ratio: float = Form(0.8, description="训练集比例"),
    val_ratio: float = Form(0.1, description="验证集比例"),
    test_ratio: float = Form(0.1, description="测试集比例"),
    current_user: User = Depends(get_current_user),
):
    """划分数据集"""
    try:
        stats = split_dataset(
            images_dir=images_dir,
            labels_dir=labels_dir,
            output_dir=output_dir,
            train_ratio=train_ratio,
            val_ratio=val_ratio,
            test_ratio=test_ratio,
        )

        return ApiResponse(code=200, message="数据集划分完成", data=stats)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/datasets/generate-yaml", response_model=ApiResponse, dependencies=[Depends(RequirePermission("training:task:create"))])
async def generate_data_yaml_api(
    output_path: str = Form(..., description="输出文件路径"),
    class_names: str = Form(..., description="类别名称，逗号分隔"),
    dataset_dir: str = Form(..., description="数据集根目录"),
    current_user: User = Depends(get_current_user),
):
    """生成 data.yaml 配置文件"""
    class_list = [name.strip() for name in class_names.split(",")]

    try:
        generate_data_yaml(output_path=output_path, class_names=class_list, dataset_dir=dataset_dir)

        return ApiResponse(code=200, message="data.yaml 生成成功", data={"path": output_path})
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/models/upload", response_model=ApiResponse, dependencies=[Depends(RequirePermission("model:create"))])
@limiter.limit("10/minute")
async def upload_model(
    request: Request,
    model_id: int = Form(..., description="所属模型ID"),
    model_file: UploadFile = File(..., description="模型文件(.pt)"),
    version: str = Form(..., description="版本号，如 v1.0.0"),
    description: str = Form("", description="版本描述"),
    is_default: bool = Form(True, description="是否设为默认版本"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """手动上传模型版本文件（归属于指定模型下）"""
    import shutil
    from pathlib import Path

    # 验证模型是否存在
    model_obj = db.query(Model).filter(Model.id == model_id).first()
    if not model_obj:
        raise HTTPException(status_code=404, detail="模型不存在")

    # 验证文件类型
    if not model_file.filename.endswith(".pt"):
        raise HTTPException(status_code=400, detail="仅支持 .pt 模型文件")

    # 创建模型存储目录
    models_dir = Path("data/models") / model_obj.name
    models_dir.mkdir(parents=True, exist_ok=True)

    # 保存模型文件
    model_filename = f"{model_obj.name}_{version}.pt"
    model_path = models_dir / model_filename

    with open(model_path, "wb") as buffer:
        shutil.copyfileobj(model_file.file, buffer)

    file_size = model_path.stat().st_size

    # 如果设为默认版本，先取消该模型其他默认版本
    if is_default:
        db.query(ModelVersion).filter(
            ModelVersion.model_id == model_id, ModelVersion.is_default.is_(True)
        ).update({"is_default": False})

    # 获取当前版本数量（用于日志记录）
    _version_count = db.query(ModelVersion).filter(ModelVersion.model_id == model_id).count()

    # 创建模型版本记录
    model_version = ModelVersion(
        model_id=model_id,
        training_task_id=None,  # 手动上传，无关联训练任务
        version=version,
        source="upload",
        status="active",
        model_path=str(model_path),
        description=description or f"手动上传于 {now_cst().strftime('%Y-%m-%d %H:%M')}",
        file_size=file_size,
        is_default=is_default,
    )
    db.add(model_version)
    db.commit()
    db.refresh(model_version)

    return ApiResponse(
        code=200,
        message="模型版本上传成功",
        data={
            "id": model_version.id,
            "model": model_obj.name,
            "version": version,
            "model_path": str(model_path),
            "file_size": file_size,
            "is_default": is_default,
        },
    )


# ── 数据集格式转换 ──────────────────────────────────


@router.post("/datasets/convert/voc-to-yolo", response_model=ApiResponse, dependencies=[Depends(RequirePermission("training:task:create"))])
async def convert_voc_to_yolo_api(
    voc_file: UploadFile = File(..., description="VOC XML 文件"),
    class_names: str = Form(..., description="类别名称，逗号分隔"),
    current_user: User = Depends(get_current_user),
):
    """VOC XML → YOLO TXT 格式转换"""
    import tempfile
    import os

    class_list = [name.strip() for name in class_names.split(",")]

    with tempfile.NamedTemporaryFile(suffix=".xml", delete=False) as tmp:
        tmp.write(await voc_file.read())
        voc_path = tmp.name

    try:
        output_dir = tempfile.mkdtemp(prefix="voc2yolo_")
        result_path = convert_voc_to_yolo(voc_path, output_dir, class_list)
        os.unlink(voc_path)

        if result_path is None:
            raise HTTPException(status_code=400, detail="VOC 转换失败")

        return ApiResponse(
            code=200, message="VOC → YOLO 转换成功", data={"output_path": result_path}
        )
    except Exception as e:
        if os.path.exists(voc_path):
            os.unlink(voc_path)
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        # 清理临时目录
        if 'output_dir' in locals() and os.path.exists(output_dir):
            import shutil as _shutil
            _shutil.rmtree(output_dir, ignore_errors=True)


@router.post("/datasets/convert/coco-to-yolo", response_model=ApiResponse, dependencies=[Depends(RequirePermission("training:task:create"))])
async def convert_coco_to_yolo_api(
    coco_file: UploadFile = File(..., description="COCO JSON 文件"),
    image_dir: str = Form(..., description="图像目录路径（用于获取图像尺寸）"),
    output_dir: str = Form(..., description="YOLO 标注输出目录"),
    current_user: User = Depends(get_current_user),
):
    """COCO JSON → YOLO TXT 格式转换"""
    import tempfile
    import os

    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
        tmp.write(await coco_file.read())
        coco_path = tmp.name

    try:
        result = convert_coco_to_yolo(coco_path, output_dir, image_dir)
        os.unlink(coco_path)

        return ApiResponse(
            code=200,
            message=f"COCO → YOLO 转换成功，共 {len(result)} 个文件",
            data={"count": len(result), "files": result},
        )
    except Exception as e:
        if os.path.exists(coco_path):
            os.unlink(coco_path)
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/datasets/convert/labelme-to-yolo", response_model=ApiResponse, dependencies=[Depends(RequirePermission("training:task:create"))])
async def convert_labelme_to_yolo_api(
    labelme_file: UploadFile = File(..., description="LabelMe JSON 文件"),
    class_names: str = Form(..., description="类别名称，逗号分隔"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """LabelMe JSON → YOLO TXT 格式转换"""
    import tempfile
    import os

    class_list = [name.strip() for name in class_names.split(",")]

    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
        tmp.write(await labelme_file.read())
        labelme_path = tmp.name

    try:
        output_dir = tempfile.mkdtemp(prefix="labelme2yolo_")
        result_path = convert_labelme_to_yolo(labelme_path, output_dir, class_list)
        os.unlink(labelme_path)

        if result_path is None:
            raise HTTPException(status_code=400, detail="LabelMe 转换失败")

        return ApiResponse(
            code=200, message="LabelMe → YOLO 转换成功", data={"output_path": result_path}
        )
    except Exception as e:
        if os.path.exists(labelme_path):
            os.unlink(labelme_path)
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        # 清理临时目录
        if 'output_dir' in locals() and os.path.exists(output_dir):
            import shutil as _shutil
            _shutil.rmtree(output_dir, ignore_errors=True)


@router.get("/models/{version_id}/download", dependencies=[Depends(RequirePermission("model:view"))])
async def download_model(
    version_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    """下载模型文件

    返回模型文件流，支持 .pt 文件下载
    """

    # 查询模型版本
    model_version = (
        db.query(ModelVersion)
        .filter(ModelVersion.id == version_id, ModelVersion.status == "active")
        .first()
    )

    if not model_version:
        raise HTTPException(status_code=404, detail="模型不存在")

    # 校验模型所有权：超级管理员可下载所有模型，其他用户只能下载自己创建的
    model_obj = db.query(Model).filter(Model.id == model_version.model_id).first()
    if not current_user.is_superuser:
        if not model_obj or model_obj.created_by != current_user.id:
            raise HTTPException(status_code=403, detail="无权下载该模型")

    # 检查模型文件是否存在
    model_path = model_version.model_path
    if not os.path.exists(model_path):
        raise HTTPException(status_code=404, detail="模型文件不存在")

    # 生成下载文件名
    model_name = model_obj.name if model_obj else "model"
    filename = f"{model_name}_{model_version.version}.pt"

    logger.info(f"用户 {current_user.username} 下载模型: {filename}")

    return FileResponse(path=model_path, filename=filename, media_type="application/octet-stream")
