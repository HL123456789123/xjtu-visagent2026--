"""
检测模块 API 路由
提供目标检测、场景管理等接口
"""
import json
import os
import tempfile
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.database.session import get_db
from app.entity.db_models import User, DetectionScene
from app.entity.schemas import ApiResponse
from app.services.detection_service import detection_service

router = APIRouter(prefix="/api/detection", tags=["目标检测"])


@router.post("/single", response_model=ApiResponse)
async def detect_single(
    scene_id: int = Form(..., description="场景ID"),
    image: UploadFile = File(..., description="图像文件"),
    conf_threshold: float = Form(0.25, description="置信度阈值"),
    iou_threshold: float = Form(0.45, description="IoU阈值"),
    image_size: int = Form(640, description="推理图像尺寸"),
    model_version_id: Optional[int] = Form(None, description="指定模型版本ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """单图检测"""
    # 验证场景
    scene = db.query(DetectionScene).filter(DetectionScene.id == scene_id).first()
    if not scene:
        raise HTTPException(status_code=404, detail="场景不存在")
    
    # 保存上传的图像
    with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp:
        content = await image.read()
        tmp.write(content)
        tmp_path = tmp.name
    
    try:
        # 执行检测
        result = await detection_service.detect_single(
            db=db,
            scene_id=scene_id,
            image_path=tmp_path,
            conf_threshold=conf_threshold,
            iou_threshold=iou_threshold,
            image_size=image_size,
            model_version_id=model_version_id
        )
        
        # 保存检测结果
        task = await detection_service.save_detection_result(
            db=db,
            user_id=current_user.id,
            scene_id=scene_id,
            task_type="single",
            detections=result["detections"],
            image_path=tmp_path,
            annotated_image_path=result.get("annotated_image_path"),
            conf_threshold=conf_threshold,
            iou_threshold=iou_threshold,
            image_size=image_size,
            inference_time=result.get("inference_time", 0),
            model_version_id=model_version_id
        )
        
        return ApiResponse(
            code=200,
            message="检测完成",
            data={
                "task_id": task.id,
                "total_objects": result["total_objects"],
                "inference_time": result["inference_time"],
                "detections": result["detections"]
            }
        )
    
    finally:
        # 清理临时文件
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


@router.post("/batch", response_model=ApiResponse)
async def detect_batch(
    scene_id: int = Form(..., description="场景ID"),
    images: List[UploadFile] = File(..., description="图像文件列表"),
    conf_threshold: float = Form(0.25, description="置信度阈值"),
    iou_threshold: float = Form(0.45, description="IoU阈值"),
    image_size: int = Form(640, description="推理图像尺寸"),
    model_version_id: Optional[int] = Form(None, description="指定模型版本ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """批量检测"""
    # 验证场景
    scene = db.query(DetectionScene).filter(DetectionScene.id == scene_id).first()
    if not scene:
        raise HTTPException(status_code=404, detail="场景不存在")
    
    # 保存上传的图像
    temp_paths = []
    for image in images:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp:
            content = await image.read()
            tmp.write(content)
            temp_paths.append(tmp.name)
    
    try:
        # 执行批量检测
        results = await detection_service.detect_batch(
            db=db,
            scene_id=scene_id,
            image_paths=temp_paths,
            conf_threshold=conf_threshold,
            iou_threshold=iou_threshold,
            image_size=image_size,
            model_version_id=model_version_id
        )
        
        # 统一保存为一个 Task + 多个 Results
        task = await detection_service.save_batch_detection_results(
            db=db,
            user_id=current_user.id,
            scene_id=scene_id,
            task_type="batch",
            batch_results=results,
            conf_threshold=conf_threshold,
            iou_threshold=iou_threshold,
            image_size=image_size,
            model_version_id=model_version_id
        )
        
        return ApiResponse(
            code=200,
            message="批量检测完成",
            data={
                "task_id": task.id,
                "total_images": len(images),
                "total_objects": task.total_objects,
                "results": results
            }
        )
    
    finally:
        # 清理临时文件
        for path in temp_paths:
            if os.path.exists(path):
                os.unlink(path)


@router.post("/folder", response_model=ApiResponse)
async def detect_folder(
    scene_id: int = Form(..., description="场景ID"),
    folder_path: str = Form(..., description="图片文件夹路径"),
    conf_threshold: float = Form(0.25, description="置信度阈值"),
    iou_threshold: float = Form(0.45, description="IoU阈值"),
    image_size: int = Form(640, description="图像尺寸"),
    model_version_id: Optional[int] = Form(None, description="指定模型版本ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """文件夹批量检测：扫描指定文件夹，对所有图片逐一检测"""
    # 验证场景
    scene = db.query(DetectionScene).filter(DetectionScene.id == scene_id).first()
    if not scene:
        raise HTTPException(status_code=404, detail="场景不存在")

    # 验证文件夹路径安全性：解析真实路径并检查是否在白名单目录内
    from app.config.settings import settings
    folder = Path(folder_path).resolve()
    if not folder.exists() or not folder.is_dir():
        raise HTTPException(status_code=400, detail=f"文件夹不存在: {folder_path}")

    allowed_dirs = [Path(d.strip()).resolve() for d in settings.ALLOWED_DETECTION_DIRS.split(",") if d.strip()]
    if allowed_dirs and not any(folder == d or d in folder.parents for d in allowed_dirs):
        raise HTTPException(
            status_code=403,
            detail=f"不允许访问该目录，仅允许以下目录: {settings.ALLOWED_DETECTION_DIRS}"
        )

    # 支持的图像扩展名
    image_extensions = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff"}
    image_files = sorted([
        str(f) for f in folder.iterdir()
        if f.suffix.lower() in image_extensions
    ])

    if not image_files:
        raise HTTPException(status_code=400, detail="文件夹中没有支持的图像文件")

    # 加载模型
    model_path = detection_service.get_default_model_path(db, scene_id, model_version_id)
    cache_key = (scene_id, model_version_id)
    detection_service.load_model(scene_id, model_path, cache_key=cache_key)

    # 创建检测任务记录
    task = await detection_service.save_detection_result(
        db=db,
        user_id=current_user.id,
        scene_id=scene_id,
        task_type="folder",
        source_path=folder_path,
        detections=[],
        output_urls=[]
    )

    # 逐文件检测
    all_detections = []
    for img_path in image_files:
        try:
            detections = await detection_service.detect_single(
                scene_id=scene_id,
                image_path=img_path,
                conf_threshold=conf_threshold,
                iou_threshold=iou_threshold,
                image_size=image_size,
                model_version_id=model_version_id
            )
            all_detections.append({
                "file": os.path.basename(img_path),
                "detections": detections
            })
        except Exception as e:
            all_detections.append({
                "file": os.path.basename(img_path),
                "error": str(e)
            })

    # 更新任务记录
    detected_count = len([d for d in all_detections if "error" not in d])
    task.result_summary = json.dumps({"total_files": len(image_files), "detected_files": detected_count})
    db.commit()

    return ApiResponse(
        code=200,
        message=f"文件夹检测完成，共处理 {len(image_files)} 个文件",
        data={
            "task_id": task.id,
            "total_files": len(image_files),
            "results": all_detections
        }
    )


@router.post("/video", response_model=ApiResponse)
async def detect_video(
    scene_id: int = Form(..., description="场景ID"),
    video: UploadFile = File(..., description="视频文件"),
    conf_threshold: float = Form(0.25, description="置信度阈值"),
    iou_threshold: float = Form(0.45, description="IoU阈值"),
    image_size: int = Form(640, description="推理图像尺寸"),
    model_version_id: Optional[int] = Form(None, description="指定模型版本ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """视频检测"""
    # 验证场景
    scene = db.query(DetectionScene).filter(DetectionScene.id == scene_id).first()
    if not scene:
        raise HTTPException(status_code=404, detail="场景不存在")
    
    # 保存上传的视频
    # 获取原始文件扩展名，保持原始格式
    original_suffix = Path(video.filename).suffix if video.filename else ".mp4"
    with tempfile.NamedTemporaryFile(delete=False, suffix=original_suffix) as tmp:
        content = await video.read()
        tmp.write(content)
        video_path = tmp.name
    
    # 输出视频路径：在原始文件名基础上添加 _detected 后缀
    video_stem = Path(video_path).stem
    video_suffix = Path(video_path).suffix
    output_path = os.path.join(
        os.path.dirname(video_path),
        f"{video_stem}_detected{video_suffix}"
    )
    
    try:
        # 执行视频检测
        result = await detection_service.detect_video(
            db=db,
            scene_id=scene_id,
            video_path=video_path,
            output_path=output_path,
            conf_threshold=conf_threshold,
            iou_threshold=iou_threshold,
            image_size=image_size,
            model_version_id=model_version_id
        )
        
        # 上传结果视频到 MinIO
        from app.storage.minio_client import minio_client
        object_name = f"detection/video/{os.path.basename(output_path)}"
        video_url = minio_client.upload_file(output_path, object_name)
        
        return ApiResponse(
            code=200,
            message="视频检测完成",
            data={
                "total_frames": result["total_frames"],
                "total_objects": result["total_objects"],
                "inference_time": result["inference_time"],
                "video_url": video_url
            }
        )
    
    finally:
        # 清理临时文件
        if os.path.exists(video_path):
            os.unlink(video_path)
        if os.path.exists(output_path):
            os.unlink(output_path)


@router.get("/tasks/{task_id}", response_model=ApiResponse)
async def get_detection_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取检测任务详情"""
    from app.entity.db_models import DetectionTask
    
    task = db.query(DetectionTask).filter(
        DetectionTask.id == task_id,
        DetectionTask.user_id == current_user.id
    ).first()
    if not task:
        raise HTTPException(status_code=404, detail="检测任务不存在")
    
    return ApiResponse(
        code=200,
        data={
            "id": task.id,
            "task_type": task.task_type,
            "status": task.status,
            "total_images": task.total_images,
            "total_objects": task.total_objects,
            "total_inference_time": task.total_inference_time,
            "conf_threshold": task.conf_threshold,
            "iou_threshold": task.iou_threshold,
            "image_size": task.image_size,
            "created_at": task.created_at.isoformat() if task.created_at else None,
            "completed_at": task.completed_at.isoformat() if task.completed_at else None
        }
    )


@router.get("/tasks/{task_id}/results", response_model=ApiResponse)
async def get_detection_results(
    task_id: int,
    page: int = 1,
    page_size: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取检测结果"""
    # 先校验任务所有权
    from app.entity.db_models import DetectionTask
    task = db.query(DetectionTask).filter(
        DetectionTask.id == task_id,
        DetectionTask.user_id == current_user.id
    ).first()
    if not task:
        raise HTTPException(status_code=404, detail="检测任务不存在")
    
    result = detection_service.get_task_results(
        db=db,
        task_id=task_id,
        page=page,
        page_size=page_size
    )
    
    return ApiResponse(code=200, data=result)


@router.get("/tasks", response_model=ApiResponse)
async def get_detection_tasks(
    scene_id: Optional[int] = None,
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取检测任务列表"""
    result = detection_service.get_task_list(
        db=db,
        user_id=current_user.id,
        scene_id=scene_id,
        page=page,
        page_size=page_size
    )
    
    return ApiResponse(code=200, data=result)


@router.get("/scenes", response_model=ApiResponse)
async def get_detection_scenes(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取检测场景列表（带 Redis 缓存）"""
    from app.storage.redis_client import redis_client
    
    # 尝试从缓存获取
    cache_key = "detection_scenes:active"
    cached = redis_client.cache_get("scenes", cache_key)
    if cached is not None:
        return ApiResponse(code=200, data=cached)
    
    # 缓存未命中，查询数据库
    scenes = db.query(DetectionScene).filter(
        DetectionScene.is_active.is_(True)
    ).all()
    
    result = [
        {
            "id": s.id,
            "name": s.name,
            "display_name": s.display_name,
            "description": s.description,
            "category": s.category,
            "class_names": s.class_names,
            "class_names_cn": s.class_names_cn
        }
        for s in scenes
    ]
    
    # 写入缓存（1小时过期）
    redis_client.cache_set("scenes", cache_key, result, ex=3600)
    
    return ApiResponse(code=200, data=result)


@router.post("/scenes", response_model=ApiResponse)
async def create_detection_scene(
    name: str = Form(..., description="场景标识"),
    display_name: str = Form(..., description="场景显示名"),
    description: str = Form("", description="场景描述"),
    category: str = Form(..., description="场景分类"),
    class_names: str = Form(..., description="类别名称，逗号分隔"),
    class_names_cn: str = Form("", description="类别中文名，逗号分隔"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """创建检测场景"""
    # 检查名称是否已存在
    existing = db.query(DetectionScene).filter(DetectionScene.name == name).first()
    if existing:
        raise HTTPException(status_code=400, detail="场景名称已存在")
    
    # 解析类别名称
    class_list = [n.strip() for n in class_names.split(",")]
    class_cn_list = [n.strip() for n in class_names_cn.split(",")] if class_names_cn else []
    
    # 构建中文名映射
    class_names_cn_dict = {}
    for i, cn in enumerate(class_cn_list):
        if i < len(class_list):
            class_names_cn_dict[class_list[i]] = cn
    
    scene = DetectionScene(
        name=name,
        display_name=display_name,
        description=description,
        category=category,
        class_names=class_list,
        class_names_cn=class_names_cn_dict if class_names_cn_dict else None,
        created_by=current_user.id
    )
    db.add(scene)
    db.commit()
    db.refresh(scene)
    
    return ApiResponse(
        code=200,
        message="场景创建成功",
        data={
            "id": scene.id,
            "name": scene.name,
            "display_name": scene.display_name
        }
    )
