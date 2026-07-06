"""
模型管理 API 路由
提供模型 CRUD、版本管理、导入导出、场景绑定等接口
"""

import os
import shutil
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask
from sqlalchemy.orm import Session

from app.core.security import get_current_user, RequirePermission
from app.core.logger import get_logger
from app.database.session import get_db
from app.entity.db_models import User, Model, DetectionScene
from app.entity.schemas import ApiResponse
from app.services.model_service import model_service

logger = get_logger("model_api")

router = APIRouter(prefix="/api/models", tags=["模型管理"])


def _check_model_ownership(db: Session, model_id: int, current_user: User):
    """校验模型所有权，不属于当前用户则抛出 403"""
    model = db.query(Model).filter(Model.id == model_id).first()
    if not model:
        raise HTTPException(status_code=404, detail="模型不存在")
    # 超级管理员直接放行
    if current_user.is_superuser:
        return model
    if model.created_by is None or model.created_by != current_user.id:
        raise HTTPException(status_code=403, detail="无权操作该模型")
    return model


# ── 模型 CRUD ────────────────────────────────────────────


@router.get("", response_model=ApiResponse, dependencies=[Depends(RequirePermission("model:view"))])
async def list_models(
    category: Optional[str] = None,
    status: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取模型列表"""
    # 超级管理员查看所有模型，普通用户仅查看自己的模型
    result = model_service.get_model_list(
        db=db,
        user_id=None if current_user.is_superuser else current_user.id,
        category=category,
        status=status,
        page=page,
        page_size=page_size,
    )
    return ApiResponse(code=200, data=result)


@router.post("", response_model=ApiResponse, dependencies=[Depends(RequirePermission("model:create"))])
async def create_model(
    name: str = Form(..., description="模型名称"),
    description: str = Form("", description="模型描述"),
    base_architecture: str = Form("yolov11n", description="基础架构"),
    category: str = Form("general", description="模型分类"),
    class_names: str = Form("[]", description="类别列表 JSON"),
    class_names_cn: str = Form("{}", description="类别中文名 JSON"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """创建模型"""
    import json

    try:
        cn_list = json.loads(class_names)
        cn_map = json.loads(class_names_cn) if class_names_cn else None
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="class_names 或 class_names_cn JSON 格式错误")

    try:
        model = model_service.create_model(
            db=db,
            user_id=current_user.id,
            name=name,
            description=description,
            base_architecture=base_architecture,
            category=category,
            class_names=cn_list,
            class_names_cn=cn_map,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return ApiResponse(
        code=200,
        message="模型创建成功",
        data={"id": model.id, "name": model.name},
    )


@router.get("/{model_id}", response_model=ApiResponse, dependencies=[Depends(RequirePermission("model:view"))])
async def get_model(
    model_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取模型详情（含版本列表和关联场景）"""
    detail = model_service.get_model_detail(db, model_id)
    if not detail:
        raise HTTPException(status_code=404, detail="模型不存在")
    return ApiResponse(code=200, data=detail)


@router.put("/{model_id}", response_model=ApiResponse, dependencies=[Depends(RequirePermission("model:update"))])
async def update_model(
    model_id: int,
    name: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    base_architecture: Optional[str] = Form(None),
    category: Optional[str] = Form(None),
    class_names: Optional[str] = Form(None),
    class_names_cn: Optional[str] = Form(None),
    status: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """更新模型信息"""
    import json

    _check_model_ownership(db, model_id, current_user)  # 校验所有权

    kwargs = {}
    if name is not None:
        kwargs["name"] = name
    if description is not None:
        kwargs["description"] = description
    if base_architecture is not None:
        kwargs["base_architecture"] = base_architecture
    if category is not None:
        kwargs["category"] = category
    if status is not None:
        kwargs["status"] = status
    if class_names is not None:
        try:
            kwargs["class_names"] = json.loads(class_names)
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="class_names JSON 格式错误")
    if class_names_cn is not None:
        try:
            kwargs["class_names_cn"] = json.loads(class_names_cn)
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="class_names_cn JSON 格式错误")

    model = model_service.update_model(db, model_id, **kwargs)
    if not model:
        raise HTTPException(status_code=404, detail="模型不存在")

    return ApiResponse(code=200, message="模型更新成功")


@router.delete("/{model_id}", response_model=ApiResponse, dependencies=[Depends(RequirePermission("model:delete"))])
async def delete_model(
    model_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """归档模型（软删除）"""
    _check_model_ownership(db, model_id, current_user)  # 校验所有权
    success = model_service.delete_model(db, model_id)
    if not success:
        raise HTTPException(status_code=404, detail="模型不存在")
    return ApiResponse(code=200, message="模型已归档")


# ── 版本管理 ──────────────────────────────────────────────


@router.get("/{model_id}/versions", response_model=ApiResponse, dependencies=[Depends(RequirePermission("model:view"))])
async def list_versions(
    model_id: int,
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取模型版本列表"""
    result = model_service.get_model_versions(db, model_id, page, page_size)
    return ApiResponse(code=200, data=result)


@router.put("/{model_id}/versions/{version_id}/default", response_model=ApiResponse, dependencies=[Depends(RequirePermission("model:update"))])
async def set_default_version(
    model_id: int,
    version_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """设为默认版本"""
    _check_model_ownership(db, model_id, current_user)  # 校验所有权
    success = model_service.set_default_version(db, model_id, version_id)
    if not success:
        raise HTTPException(status_code=404, detail="版本不存在")
    return ApiResponse(code=200, message="已设为默认版本")


@router.delete("/{model_id}/versions/{version_id}", response_model=ApiResponse, dependencies=[Depends(RequirePermission("model:delete"))])
async def delete_version(
    model_id: int,
    version_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """归档模型版本"""
    _check_model_ownership(db, model_id, current_user)  # 校验所有权
    success = model_service.delete_model_version(db, version_id)
    if not success:
        raise HTTPException(status_code=404, detail="版本不存在")
    return ApiResponse(code=200, message="版本已归档")


# ── 导入导出 ──────────────────────────────────────────────


@router.get("/{model_id}/versions/{version_id}/export", dependencies=[Depends(RequirePermission("model:view"))])
async def export_model(
    model_id: int,
    version_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """导出模型 ZIP 包"""
    _check_model_ownership(db, model_id, current_user)  # 校验所有权
    zip_path = model_service.export_model(db, model_id, version_id)
    if not zip_path or not os.path.exists(zip_path):
        raise HTTPException(status_code=400, detail="导出失败，请检查模型文件是否存在")

    filename = os.path.basename(zip_path)
    logger.info(f"用户 {current_user.username} 导出模型: {filename}")

    return FileResponse(
        path=zip_path,
        filename=filename,
        media_type="application/zip",
        background=BackgroundTask(shutil.rmtree, os.path.dirname(zip_path), ignore_errors=True),
    )


@router.post("/{model_id}/import", response_model=ApiResponse, dependencies=[Depends(RequirePermission("model:create"))])
async def import_model(
    model_id: int,
    zip_file: UploadFile = File(..., description="模型 ZIP 包"),
    description: str = Form("", description="版本描述"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """从 ZIP 导入模型版本"""
    import tempfile

    _check_model_ownership(db, model_id, current_user)  # 校验所有权

    # 保存上传的 ZIP 到临时文件
    with tempfile.NamedTemporaryFile(delete=False, suffix=".zip") as tmp:
        content = await zip_file.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        mv = model_service.import_model(db, model_id, tmp_path, description)
        if not mv:
            raise HTTPException(status_code=400, detail="导入失败，请检查 ZIP 格式")

        return ApiResponse(
            code=200,
            message="模型版本导入成功",
            data={
                "id": mv.id,
                "version": mv.version,
                "model_path": mv.model_path,
            },
        )
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


# ── 场景绑定 ──────────────────────────────────────────────


@router.get("/scenes/{scene_id}/models", response_model=ApiResponse, dependencies=[Depends(RequirePermission("model:view"))])
async def list_scene_models(
    scene_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取场景关联的模型列表"""

    scene = db.query(DetectionScene).filter(DetectionScene.id == scene_id).first()
    if not scene:
        raise HTTPException(status_code=404, detail="场景不存在")

    result = model_service.get_scene_models(db, scene_id)
    return ApiResponse(code=200, data=result)


@router.post("/scenes/{scene_id}/bindmodel", response_model=ApiResponse, dependencies=[Depends(RequirePermission("model:update"))])
async def bind_model_to_scene(
    scene_id: int,
    model_id: int = Form(..., description="模型ID"),
    is_default: bool = Form(False, description="是否设为场景默认模型"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """绑定模型到场景"""

    scene = db.query(DetectionScene).filter(DetectionScene.id == scene_id).first()
    if not scene:
        raise HTTPException(status_code=404, detail="场景不存在")

    model = db.query(Model).filter(Model.id == model_id).first()
    if not model:
        raise HTTPException(status_code=404, detail="模型不存在")

    sm = model_service.bind_model_to_scene(db, scene_id, model_id, is_default)
    return ApiResponse(code=200, message="模型绑定成功", data={"scene_model_id": sm.id})


@router.delete("/scenes/{scene_id}/bindmodel/{model_id}", response_model=ApiResponse, dependencies=[Depends(RequirePermission("model:update"))])
async def unbind_model_from_scene(
    scene_id: int,
    model_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """解绑模型与场景"""
    success = model_service.unbind_model_from_scene(db, scene_id, model_id)
    if not success:
        raise HTTPException(status_code=404, detail="绑定关系不存在")
    return ApiResponse(code=200, message="模型已解绑")
