"""
数据集管理 API 路由
提供数据集注册、列表、详情、删除、校验等接口
"""

from pathlib import Path
from typing import Optional
import os

import yaml
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.config.settings import settings
from app.core.security import get_current_user, RequirePermission, is_super_admin
from app.core.logger import get_logger
from app.database.session import get_db
from app.entity.db_models import User, Dataset
from app.entity.schemas import ApiResponse
from app.core.rate_limiter import limiter
from app.storage.redis_client import redis_client

logger = get_logger("dataset_api")

router = APIRouter(prefix="/api/datasets", tags=["数据集管理"])


def _get_allowed_dirs() -> list[Path]:
    """获取白名单目录列表"""
    return [
        Path(d.strip()).resolve()
        for d in settings.ALLOWED_TRAINING_DIRS.split(",")
        if d.strip()
    ]


def _is_path_allowed(resolved: Path) -> bool:
    """检查路径是否在白名单内"""
    resolved_str = str(resolved)
    return any(
        resolved_str == str(allowed) or resolved_str.startswith(str(allowed) + '/')
        for allowed in _get_allowed_dirs()
    )


def _validate_path(file_path: str, label: str = "路径") -> Path:
    """校验路径是否在白名单目录内，返回 resolved Path"""
    resolved = Path(file_path).resolve()
    allowed_dirs = _get_allowed_dirs()
    for allowed in allowed_dirs:
        try:
            resolved.relative_to(allowed)
            return resolved
        except ValueError:
            continue
    raise HTTPException(
        status_code=400,
        detail=f"{label}不在允许的目录内，允许的目录: {', '.join(str(d) for d in allowed_dirs)}",
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
    """统计数据集目录下的图片数量（限制扫描深度，避免性能问题）"""
    if not dataset_path.exists():
        raise HTTPException(status_code=400, detail=f"数据集目录不存在: {dataset_path}")

    image_extensions = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp"}
    count = 0

    # 查找 images 子目录
    images_dir = dataset_path / "images"
    scan_dir = images_dir if images_dir.is_dir() else dataset_path
    for f in _walk_with_depth_limit(scan_dir, max_depth=3):
        if f.suffix.lower() in image_extensions:
            count += 1

    return count


class DatasetCreateRequest(BaseModel):
    name: str
    description: Optional[str] = None
    path: str
    yaml_path: str
    format: str = "yolo"
    scene_id: Optional[int] = None  # 关联检测场景


@router.get("/browse", response_model=ApiResponse, dependencies=[Depends(RequirePermission("dataset:create"))])
async def browse_directory(
    path: Optional[str] = None,
    current_user: User = Depends(get_current_user),
):
    """浏览服务器目录（白名单内）

    - path 为空时：返回白名单根目录列表
    - path 非空时：返回该目录下的子目录和 yaml 文件
    """
    if not path:
        # 返回白名单根目录
        roots = []
        for d in _get_allowed_dirs():
            if d.exists():
                roots.append({"name": d.name or str(d), "path": str(d)})
        return ApiResponse(code=200, data={"current_path": None, "dirs": roots, "yaml_files": []})

    # 校验路径合法性
    resolved = Path(path).resolve()
    if not _is_path_allowed(resolved):
        raise HTTPException(status_code=403, detail="无权浏览该目录")

    if not resolved.exists():
        raise HTTPException(status_code=404, detail="目录不存在")

    if not resolved.is_dir():
        raise HTTPException(status_code=400, detail="不是目录")

    dirs = []
    yaml_files = []

    try:
        for item in sorted(resolved.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower())):
            if item.name.startswith("."):
                continue
            if item.is_dir():
                dirs.append({"name": item.name, "path": str(item)})
            elif item.suffix.lower() in (".yaml", ".yml"):
                yaml_files.append({"name": item.name, "path": str(item)})
    except PermissionError:
        raise HTTPException(status_code=403, detail="无权限读取该目录")

    return ApiResponse(
        code=200,
        data={
            "current_path": str(resolved),
            "dirs": dirs,
            "yaml_files": yaml_files,
        },
    )


def _walk_with_depth_limit(root_dir: Path, max_depth: int = 5):
    """递归遍历目录，限制最大扫描深度

    Args:
        root_dir: 根目录
        max_depth: 最大递归深度（相对根目录）

    Yields:
        Path 对象
    """
    root_depth = len(root_dir.parts)
    for dirpath, dirnames, filenames in os.walk(root_dir):
        current = Path(dirpath)
        # 跳过隐藏目录
        dirnames[:] = [d for d in dirnames if not d.startswith(".")]
        current_depth = len(current.parts) - root_depth
        if current_depth >= max_depth:
            dirnames.clear()  # 不再递归进入子目录
            continue
        for filename in filenames:
            yield current / filename


@router.get("/discover", response_model=ApiResponse, dependencies=[Depends(RequirePermission("dataset:create"))])
async def discover_datasets(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """扫描白名单目录，自动发现未注册的数据集

    查找标准：目录下存在 data.yaml 或 data.yml 配置文件
    递归扫描所有子目录（无深度限制）
    结果缓存 5 分钟，减少重复扫描开销
    """
    # 尝试从 Redis 缓存获取
    cache_key = "dataset_discover"
    cached = redis_client.cache_get("datasets", cache_key)
    if cached:
        return ApiResponse(code=200, data=cached)

    discovered = []
    yaml_names = ("data.yaml", "data.yml")
    # 记录已处理的目录，避免重复
    processed_paths = set()

    for root_dir in _get_allowed_dirs():
        if not root_dir.exists():
            continue
        # 带深度限制扫描（最大 5 层），避免无限递归遍历大目录
        for yaml_file in _walk_with_depth_limit(root_dir, max_depth=5):
            if not yaml_file.is_file() or yaml_file.name.lower() not in yaml_names:
                continue
            # 跳过隐藏目录下的文件
            if any(part.startswith(".") for part in yaml_file.parts):
                continue

            dataset_path = yaml_file.parent
            path_str = str(dataset_path)

            # 避免重复
            if path_str in processed_paths:
                continue
            processed_paths.add(path_str)

            # 检查是否已注册
            existing = db.query(Dataset).filter(Dataset.path == path_str).first()
            if existing:
                continue

            # 尝试解析 yaml
            try:
                info = _parse_yaml_info(yaml_file)
                num_images = _count_images(dataset_path)
                discovered.append({
                    "path": path_str,
                    "yaml_path": str(yaml_file),
                    "name": dataset_path.name,
                    "num_classes": info["num_classes"],
                    "class_names": info["class_names"],
                    "num_images": num_images,
                })
            except Exception:
                # 解析失败的也列出来，但标记为未知
                discovered.append({
                    "path": path_str,
                    "yaml_path": str(yaml_file),
                    "name": dataset_path.name,
                    "num_classes": 0,
                    "class_names": [],
                    "num_images": 0,
                    "error": "配置文件解析失败",
                })

    result = {"discovered": discovered, "total": len(discovered)}
    # 写入缓存，5 分钟 TTL
    redis_client.cache_set("datasets", cache_key, result, ex=300)

    return ApiResponse(
        code=200,
        data=result,
    )




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
        scene_id=body.scene_id,
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
            "scene_id": dataset.scene_id,
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
                    "scene_id": d.scene_id,
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
            "scene_id": dataset.scene_id,
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
