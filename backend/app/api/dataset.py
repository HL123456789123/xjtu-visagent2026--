"""
数据集管理 API 路由
提供数据集注册、列表、详情、删除、校验等接口
"""

from pathlib import Path
from typing import Optional

import yaml
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.config.settings import settings
from app.core.security import get_current_user, RequirePermission
from app.core.logger import get_logger
from app.database.session import get_db
from app.entity.db_models import User, Dataset
from app.entity.schemas import ApiResponse
from app.core.rate_limiter import limiter

logger = get_logger("dataset_api")

router = APIRouter(prefix="/api/datasets", tags=["数据集管理"])


def _validate_path(file_path: str, label: str = "路径") -> Path:
    """校验路径是否在白名单目录内，返回 resolved Path"""
    resolved = Path(file_path).resolve()
    allowed_dirs = [d.strip() for d in settings.ALLOWED_TRAINING_DIRS.split(",") if d.strip()]
    for allowed in allowed_dirs:
        try:
            resolved.relative_to(Path(allowed).resolve())
            return resolved
        except ValueError:
            continue
    raise HTTPException(
        status_code=400,
        detail=f"{label}不在允许的目录内，允许的目录: {', '.join(allowed_dirs)}",
    )


def _parse_yaml_info(yaml_path: Path) -> dict:
    """解析 data.yaml，提取类别信息"""
    if not yaml_path.exists():
        raise HTTPException(status_code=400, detail=f"配置文件不存在: {yaml_path}")

    try:
        with open(yaml_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"解析 YAML 失败: {e}")

    if not data or not isinstance(data, dict):
        raise HTTPException(status_code=400, detail="YAML 文件格式错误")

    # 提取类别名称
    names = data.get("names", [])
    if isinstance(names, dict):
        class_names = list(names.values())
    elif isinstance(names, list):
        class_names = names
    else:
        class_names = []

    return {
        "class_names": class_names,
        "num_classes": len(class_names),
    }


def _count_images(dataset_path: Path) -> int:
    """统计数据集目录下的图片数量"""
    if not dataset_path.exists():
        raise HTTPException(status_code=400, detail=f"数据集目录不存在: {dataset_path}")

    image_extensions = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp"}
    count = 0

    # 查找 images 子目录
    images_dir = dataset_path / "images"
    if images_dir.is_dir():
        for f in images_dir.rglob("*"):
            if f.suffix.lower() in image_extensions:
                count += 1
    else:
        # 如果没有 images 子目录，直接统计根目录
        for f in dataset_path.rglob("*"):
            if f.suffix.lower() in image_extensions:
                count += 1

    return count


class DatasetCreateRequest(BaseModel):
    name: str
    description: Optional[str] = None
    path: str
    yaml_path: str
    format: str = "yolo"


@router.post("/register", response_model=ApiResponse, dependencies=[Depends(RequirePermission("dataset:create"))])
@limiter.limit("20/minute")
async def register_dataset(
    request: Request,
    body: DatasetCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """注册数据集（JSON Body 方式）

    自动校验路径、解析 data.yaml、统计图片数量
    """
    # 1. 校验路径白名单
    dataset_path = _validate_path(body.path, "数据集路径")
    yaml_path = _validate_path(body.yaml_path, "配置文件路径")

    # 2. 解析 YAML
    yaml_info = _parse_yaml_info(yaml_path)

    # 3. 统计图片数量
    num_images = _count_images(dataset_path)

    if num_images == 0:
        raise HTTPException(status_code=400, detail="数据集目录下未找到任何图片文件")

    # 4. 检查是否已存在同名数据集
    existing = db.query(Dataset).filter(
        Dataset.name == body.name,
        Dataset.user_id == current_user.id,
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"已存在同名数据集: {body.name}")

    # 5. 创建数据集记录
    dataset = Dataset(
        user_id=current_user.id,
        name=body.name,
        description=body.description,
        path=str(dataset_path),
        yaml_path=str(yaml_path),
        num_images=num_images,
        num_classes=yaml_info["num_classes"],
        class_names=yaml_info["class_names"],
        format=body.format,
        status="active",
    )
    db.add(dataset)
    db.commit()
    db.refresh(dataset)

    logger.info(f"用户 {current_user.username} 注册数据集: {body.name} ({num_images} 张图片)")

    return ApiResponse(
        code=200,
        message="数据集注册成功",
        data={
            "id": dataset.id,
            "name": dataset.name,
            "path": dataset.path,
            "yaml_path": dataset.yaml_path,
            "num_images": dataset.num_images,
            "num_classes": dataset.num_classes,
            "class_names": dataset.class_names,
            "format": dataset.format,
            "status": dataset.status,
        },
    )


@router.get("", response_model=ApiResponse, dependencies=[Depends(RequirePermission("dataset:view"))])
async def list_datasets(
    status: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取数据集列表"""
    query = db.query(Dataset)

    # 非超级管理员只能看自己的
    from app.core.security import is_super_admin
    if not is_super_admin(current_user, db):
        query = query.filter(Dataset.user_id == current_user.id)

    if status:
        query = query.filter(Dataset.status == status)

    total = query.count()
    items = (
        query.order_by(Dataset.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return ApiResponse(
        code=200,
        data={
            "total": total,
            "page": page,
            "page_size": page_size,
            "items": [
                {
                    "id": d.id,
                    "name": d.name,
                    "description": d.description,
                    "path": d.path,
                    "yaml_path": d.yaml_path,
                    "num_images": d.num_images,
                    "num_classes": d.num_classes,
                    "class_names": d.class_names,
                    "format": d.format,
                    "status": d.status,
                    "created_at": d.created_at.isoformat() if d.created_at else None,
                    "updated_at": d.updated_at.isoformat() if d.updated_at else None,
                }
                for d in items
            ],
        },
    )


@router.get("/{dataset_id}", response_model=ApiResponse, dependencies=[Depends(RequirePermission("dataset:view"))])
async def get_dataset(
    dataset_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取数据集详情"""
    dataset = db.query(Dataset).filter(Dataset.id == dataset_id).first()
    if not dataset:
        raise HTTPException(status_code=404, detail="数据集不存在")

    from app.core.security import is_super_admin
    if not is_super_admin(current_user, db) and dataset.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权查看该数据集")

    # 统计关联的训练任务数
    task_count = len(dataset.training_tasks) if dataset.training_tasks else 0

    return ApiResponse(
        code=200,
        data={
            "id": dataset.id,
            "name": dataset.name,
            "description": dataset.description,
            "path": dataset.path,
            "yaml_path": dataset.yaml_path,
            "num_images": dataset.num_images,
            "num_classes": dataset.num_classes,
            "class_names": dataset.class_names,
            "format": dataset.format,
            "status": dataset.status,
            "task_count": task_count,
            "created_at": dataset.created_at.isoformat() if dataset.created_at else None,
            "updated_at": dataset.updated_at.isoformat() if dataset.updated_at else None,
        },
    )


@router.delete("/{dataset_id}", response_model=ApiResponse, dependencies=[Depends(RequirePermission("dataset:manage"))])
async def delete_dataset(
    dataset_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """删除数据集（仅删除注册记录，不删除实际文件）"""
    dataset = db.query(Dataset).filter(Dataset.id == dataset_id).first()
    if not dataset:
        raise HTTPException(status_code=404, detail="数据集不存在")

    from app.core.security import is_super_admin
    if not is_super_admin(current_user, db) and dataset.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权删除该数据集")

    # 检查是否有关联的训练任务
    if dataset.training_tasks:
        running = [t for t in dataset.training_tasks if t.status in ("running", "paused", "pending")]
        if running:
            raise HTTPException(
                status_code=400,
                detail=f"该数据集有 {len(running)} 个进行中的训练任务，请先取消后再删除",
            )

    name = dataset.name
    db.delete(dataset)
    db.commit()

    logger.info(f"用户 {current_user.username} 删除数据集: {name}")
    return ApiResponse(code=200, message="数据集已删除")


@router.post("/{dataset_id}/validate", response_model=ApiResponse, dependencies=[Depends(RequirePermission("dataset:manage"))])
async def validate_dataset(
    dataset_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """重新校验数据集完整性"""
    dataset = db.query(Dataset).filter(Dataset.id == dataset_id).first()
    if not dataset:
        raise HTTPException(status_code=404, detail="数据集不存在")

    from app.core.security import is_super_admin
    if not is_super_admin(current_user, db) and dataset.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权操作该数据集")

    issues = []

    # 检查目录是否存在
    dataset_path = Path(dataset.path)
    if not dataset_path.exists():
        issues.append(f"数据集目录不存在: {dataset.path}")
        dataset.status = "invalid"
    else:
        # 重新统计图片
        num_images = _count_images(dataset_path)
        if num_images == 0:
            issues.append("数据集目录下未找到图片文件")
            dataset.status = "invalid"
        else:
            dataset.num_images = num_images

    # 检查 yaml 文件
    yaml_path = Path(dataset.yaml_path)
    if not yaml_path.exists():
        issues.append(f"配置文件不存在: {dataset.yaml_path}")
        dataset.status = "invalid"
    else:
        try:
            yaml_info = _parse_yaml_info(yaml_path)
            dataset.num_classes = yaml_info["num_classes"]
            dataset.class_names = yaml_info["class_names"]
        except Exception as e:
            issues.append(f"YAML 解析失败: {e}")
            dataset.status = "invalid"

    if not issues:
        dataset.status = "active"

    db.commit()

    return ApiResponse(
        code=200,
        message="校验完成" if not issues else "校验发现问题",
        data={
            "status": dataset.status,
            "issues": issues,
            "num_images": dataset.num_images,
            "num_classes": dataset.num_classes,
        },
    )
