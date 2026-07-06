"""
检测服务模块
提供 YOLOv11 目标检测的完整业务逻辑
包括单图检测、批量检测、文件夹检测、视频检测等
"""

import gc
import os
import tempfile
import threading
import time
from collections import OrderedDict
from pathlib import Path
from typing import Dict, List, Optional, Any

import cv2
from sqlalchemy.orm import Session

from app.core.logger import get_logger
from app.core.tz import now_cst
from app.entity.db_models import (
    DetectionTask,
    DetectionResult,
    DetectionScene,
    ModelVersion,
    SceneModel,
)
from app.storage.minio_client import MinIOClient

logger = get_logger("detection_service")


class DetectionService:
    """检测服务类"""

    MAX_CACHED_MODELS = 5  # 最多缓存 5 个模型

    def __init__(self):
        self.models: OrderedDict = OrderedDict()  # LRU 缓存
        self.minio_client = None
        self._models_lock = threading.Lock()

    def load_model(self, scene_id: int, model_path: str, cache_key=None) -> bool:
        """
        加载场景对应的模型

        Args:
            scene_id: 场景ID
            model_path: 模型文件路径
            cache_key: 缓存key，默认为 (scene_id, None)

        Returns:
            是否加载成功
        """
        if cache_key is None:
            cache_key = (scene_id, None)
        try:
            from ultralytics import YOLO

            # ultralytics 支持自动下载预训练模型（如 yolo11n.pt），
            # 本地文件不存在时由 YOLO() 内部处理下载，此处不做预检查
            if not os.path.exists(model_path):
                logger.info(f"模型文件未缓存，将由 ultralytics 自动下载: {model_path}")

            with self._models_lock:
                # 如果已缓存，移到末尾（LRU）
                if cache_key in self.models:
                    self.models.move_to_end(cache_key)
                else:
                    # 缓存已满，淘汰最久未使用的
                    if len(self.models) >= self.MAX_CACHED_MODELS:
                        oldest_key, oldest_model = self.models.popitem(last=False)
                        # 释放 YOLO 模型占用的资源（含 GPU 显存）
                        try:
                            if hasattr(oldest_model, "model"):
                                oldest_model.model.cpu()
                        except Exception:
                            pass
                        del oldest_model
                        gc.collect()
                        logger.info(f"淘汰模型缓存: {oldest_key}")
                    self.models[cache_key] = YOLO(model_path)
            logger.info(
                f"加载模型成功: scene_id={scene_id}, path={model_path}, cache_key={cache_key}"
            )
            return True
        except Exception as e:
            logger.error(f"加载模型失败: scene_id={scene_id}, path={model_path}, error={e}")
            return False

    def get_default_model_path(
        self, db: Session, scene_id: int, model_version_id: Optional[int] = None
    ) -> Optional[str]:
        """
        获取场景的默认模型路径

        查找优先级：
        1. 指定的 model_version_id
        2. 场景中 is_default=True 的关联模型
        3. 模型列表中 is_default=True 的版本
        4. 回退到预训练模型

        Args:
            db: 数据库会话
            scene_id: 场景ID
            model_version_id: 指定的模型版本ID（可选）

        Returns:
            模型路径
        """
        # 1. 如果指定了模型版本，直接使用
        if model_version_id:
            mv = (
                db.query(ModelVersion)
                .filter(ModelVersion.id == model_version_id, ModelVersion.status == "active")
                .first()
            )
            if mv:
                return mv.model_path
            logger.warning(f"指定的模型版本不存在或已归档: model_version_id={model_version_id}")

        # 2. 通过 SceneModel 关联表查找场景默认模型
        scene_model = (
            db.query(SceneModel)
            .filter(SceneModel.scene_id == scene_id, SceneModel.is_default.is_(True))
            .first()
        )

        if scene_model:
            # 查找该模型的默认版本
            mv = (
                db.query(ModelVersion)
                .filter(
                    ModelVersion.model_id == scene_model.model_id,
                    ModelVersion.is_default.is_(True),
                    ModelVersion.status == "active",
                )
                .first()
            )
            if mv:
                return mv.model_path
            # 如果没有默认版本，取最新的活跃版本
            mv = (
                db.query(ModelVersion)
                .filter(
                    ModelVersion.model_id == scene_model.model_id, ModelVersion.status == "active"
                )
                .order_by(ModelVersion.created_at.desc())
                .first()
            )
            if mv:
                return mv.model_path

        # 3. 回退到预训练模型
        return "yolo11n.pt"

    async def detect_single(
        self,
        db: Session,
        scene_id: int,
        image_path: str,
        conf_threshold: float = 0.25,
        iou_threshold: float = 0.45,
        image_size: int = 640,
        model_version_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        单图检测

        Args:
            db: 数据库会话
            scene_id: 场景ID
            image_path: 图像路径
            conf_threshold: 置信度阈值
            iou_threshold: IoU 阈值
            image_size: 推理图像尺寸
            model_version_id: 指定的模型版本ID（可选）

        Returns:
            检测结果
        """
        start_time = time.time()

        # 使用场景+模型版本组合作为缓存 key
        cache_key = (scene_id, model_version_id)

        # 确保模型已加载（load_model 是同步操作，通过 to_thread 避免阻塞事件循环）
        if cache_key not in self.models:
            model_path = self.get_default_model_path(db, scene_id, model_version_id)
            import asyncio

            loaded = await asyncio.to_thread(self.load_model, scene_id, model_path, cache_key)
            if not loaded:
                raise ValueError(f"无法加载模型: scene_id={scene_id}")

        model = self.models[cache_key]

        # 执行检测（同步阻塞操作，委托到线程池）
        import asyncio

        results = await asyncio.to_thread(
            model.predict,
            source=image_path,
            conf=conf_threshold,
            iou=iou_threshold,
            imgsz=image_size,
            verbose=False,
        )

        inference_time = (time.time() - start_time) * 1000  # 转换为毫秒

        # 解析结果
        detections = []
        annotated_image_path = None
        if results and len(results) > 0:
            result = results[0]
            img_height, img_width = result.orig_shape

            # 生成标注图像
            try:
                annotated_dir = os.path.join(tempfile.gettempdir(), "visagent_annotated")
                os.makedirs(annotated_dir, exist_ok=True)
                annotated_image_path = os.path.join(
                    annotated_dir, f"annotated_{os.path.basename(image_path)}"
                )
                result.save(filename=annotated_image_path)
            except Exception as e:
                logger.warning(f"保存标注图像失败: {e}")

            for box in result.boxes:
                class_id = int(box.cls[0])
                class_name = result.names[class_id]
                confidence = float(box.conf[0])
                bbox = box.xyxy[0].tolist()  # [x1, y1, x2, y2]

                detections.append(
                    {
                        "class_id": class_id,
                        "class_name": class_name,
                        "confidence": confidence,
                        "bbox": bbox,
                        "image_width": img_width,
                        "image_height": img_height,
                    }
                )

        return {
            "image_path": image_path,
            "annotated_image_path": annotated_image_path,
            "detections": detections,
            "total_objects": len(detections),
            "inference_time": inference_time,
            "conf_threshold": conf_threshold,
            "iou_threshold": iou_threshold,
            "image_size": image_size,
        }

    def _detect_batch_sync(
        self,
        scene_id: int,
        image_paths: List[str],
        conf_threshold: float = 0.25,
        iou_threshold: float = 0.45,
        image_size: int = 640,
        model_version_id: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        批量检测（同步版本）—— 利用 YOLO 内置 batch predict 一次性推理
        可被 asyncio.to_thread 包装以避免阻塞事件循环
        """
        if not image_paths:
            return []

        start_time = time.time()
        cache_key = (scene_id, model_version_id)

        # 确保模型已加载
        if cache_key not in self.models:
            logger.warning(f"模型未缓存，将在同步方法中加载: cache_key={cache_key}")
            # 同步方法中无法访问 db，需要调用方确保模型已加载
            if cache_key not in self.models:
                return [{"image_path": p, "error": "模型未加载", "detections": []} for p in image_paths]

        model = self.models[cache_key]

        # 一次性批量推理
        try:
            all_results = model.predict(
                source=image_paths,
                conf=conf_threshold,
                iou=iou_threshold,
                imgsz=image_size,
                verbose=False,
            )
        except Exception as e:
            logger.error(f"批量推理失败: {e}")
            return [{"image_path": p, "error": str(e), "detections": []} for p in image_paths]

        total_inference = (time.time() - start_time) * 1000
        per_image_time = total_inference / len(image_paths) if image_paths else 0

        # 逐结果解析
        results = []
        for i, result in enumerate(all_results):
            image_path = image_paths[i] if i < len(image_paths) else f"unknown_{i}"
            detections = []
            annotated_image_path = None

            try:
                img_height, img_width = result.orig_shape

                try:
                    annotated_dir = os.path.join(tempfile.gettempdir(), "visagent_annotated")
                    os.makedirs(annotated_dir, exist_ok=True)
                    annotated_image_path = os.path.join(
                        annotated_dir, f"annotated_{os.path.basename(image_path)}"
                    )
                    result.save(filename=annotated_image_path)
                except Exception as e:
                    logger.warning(f"保存标注图像失败: {e}")

                for box in result.boxes:
                    class_id = int(box.cls[0])
                    class_name = result.names[class_id]
                    confidence = float(box.conf[0])
                    bbox = box.xyxy[0].tolist()

                    detections.append(
                        {
                            "class_id": class_id,
                            "class_name": class_name,
                            "confidence": confidence,
                            "bbox": bbox,
                            "image_width": img_width,
                            "image_height": img_height,
                        }
                    )
            except Exception as e:
                logger.error(f"解析检测结果失败 {image_path}: {e}")
                results.append({"image_path": image_path, "error": str(e), "detections": []})
                continue

            results.append(
                {
                    "image_path": image_path,
                    "annotated_image_path": annotated_image_path,
                    "detections": detections,
                    "total_objects": len(detections),
                    "inference_time": per_image_time,
                    "conf_threshold": conf_threshold,
                    "iou_threshold": iou_threshold,
                    "image_size": image_size,
                }
            )

        return results

    async def detect_batch(
        self,
        db: Session,
        scene_id: int,
        image_paths: List[str],
        conf_threshold: float = 0.25,
        iou_threshold: float = 0.45,
        image_size: int = 640,
        model_version_id: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        批量检测 — 利用 YOLO 内置 batch predict，通过 asyncio.to_thread 避免阻塞事件循环
        """
        import asyncio

        # 确保模型已加载（在 async 上下文中操作）
        cache_key = (scene_id, model_version_id)
        if cache_key not in self.models:
            model_path = self.get_default_model_path(db, scene_id, model_version_id)
            loaded = await asyncio.to_thread(self.load_model, scene_id, model_path, cache_key)
            if not loaded:
                raise ValueError(f"无法加载模型: scene_id={scene_id}")

        # 在线程中执行同步推理，避免阻塞事件循环
        return await asyncio.to_thread(
            self._detect_batch_sync,
            scene_id=scene_id,
            image_paths=image_paths,
            conf_threshold=conf_threshold,
            iou_threshold=iou_threshold,
            image_size=image_size,
            model_version_id=model_version_id,
        )

    async def detect_video(
        self,
        db: Session,
        scene_id: int,
        video_path: str,
        output_path: str,
        conf_threshold: float = 0.25,
        iou_threshold: float = 0.45,
        image_size: int = 640,
        progress_callback=None,
        model_version_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        视频检测（异步版本）

        使用 asyncio.to_thread 避免阻塞事件循环

        Args:
            db: 数据库会话
            scene_id: 场景ID
            video_path: 视频路径
            output_path: 输出视频路径
            conf_threshold: 置信度阈值
            iou_threshold: IoU 阈值
            image_size: 推理图像尺寸
            progress_callback: 进度回调函数

        Returns:
            检测结果
        """
        import asyncio

        # 在线程中执行同步的视频处理
        result = await asyncio.to_thread(
            self._detect_video_sync,
            db=db,
            scene_id=scene_id,
            video_path=video_path,
            output_path=output_path,
            conf_threshold=conf_threshold,
            iou_threshold=iou_threshold,
            image_size=image_size,
            progress_callback=progress_callback,
            model_version_id=model_version_id,
        )
        return result

    def _detect_video_sync(
        self,
        db: Session,
        scene_id: int,
        video_path: str,
        output_path: str,
        conf_threshold: float = 0.25,
        iou_threshold: float = 0.45,
        image_size: int = 640,
        progress_callback=None,
        model_version_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        视频检测（同步实现）

        Args:
            db: 数据库会话
            scene_id: 场景ID
            video_path: 视频路径
            output_path: 输出视频路径
            conf_threshold: 置信度阈值
            iou_threshold: IoU 阈值
            image_size: 推理图像尺寸
            progress_callback: 进度回调函数

        Returns:
            检测结果
        """
        # 确保模型已加载
        cache_key = (scene_id, model_version_id)
        if cache_key not in self.models:
            model_path = self.get_default_model_path(db, scene_id, model_version_id)
            if not self.load_model(scene_id, model_path, cache_key=cache_key):
                raise ValueError(f"无法加载模型: scene_id={scene_id}")

        model = self.models[cache_key]

        # 打开视频
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise ValueError(f"无法打开视频: {video_path}")

        # 获取视频属性
        fps = int(cap.get(cv2.CAP_PROP_FPS))
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

        # 创建视频写入器
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))

        frame_count = 0
        total_objects = 0
        start_time = time.time()

        try:
            while True:
                ret, frame = cap.read()
                if not ret:
                    break

                # 执行检测
                results = model.predict(
                    source=frame,
                    conf=conf_threshold,
                    iou=iou_threshold,
                    imgsz=image_size,
                    verbose=False,
                )

                # 绘制检测结果
                if results and len(results) > 0:
                    annotated_frame = results[0].plot()
                    out.write(annotated_frame)
                    total_objects += len(results[0].boxes)
                else:
                    out.write(frame)

                frame_count += 1

                # 更新进度
                if progress_callback and total_frames > 0:
                    progress = int((frame_count / total_frames) * 100)
                    progress_callback(progress)

            inference_time = (time.time() - start_time) * 1000

            return {
                "video_path": video_path,
                "output_path": output_path,
                "total_frames": frame_count,
                "total_objects": total_objects,
                "inference_time": inference_time,
                "fps": fps,
            }

        finally:
            cap.release()
            out.release()

    async def save_detection_result(
        self,
        db: Session,
        user_id: int,
        scene_id: int,
        task_type: str,
        detections: List[Dict[str, Any]],
        image_path: str,
        annotated_image_path: Optional[str] = None,
        conf_threshold: float = 0.25,
        iou_threshold: float = 0.45,
        image_size: int = 640,
        inference_time: float = 0,
        model_version_id: Optional[int] = None,
    ) -> DetectionTask:
        """
        保存检测结果到数据库

        Args:
            db: 数据库会话
            user_id: 用户ID
            scene_id: 场景ID
            task_type: 检测类型
            detections: 检测结果列表
            image_path: 原始图像路径
            annotated_image_path: 标注图像路径
            conf_threshold: 置信度阈值
            iou_threshold: IoU 阈值
            image_size: 推理图像尺寸
            model_version_id: 使用的模型版本ID（可选）

        Returns:
            检测任务
        """
        # 创建检测任务
        task = DetectionTask(
            user_id=user_id,
            scene_id=scene_id,
            task_type=task_type,
            status="completed",
            total_images=1,
            total_objects=len(detections),
            total_inference_time=inference_time,
            conf_threshold=conf_threshold,
            iou_threshold=iou_threshold,
            image_size=image_size,
            completed_at=now_cst(),
        )
        # 记录使用的模型版本（如果有的话）
        if model_version_id:
            task.model_version_id = model_version_id
        db.add(task)
        db.flush()

        # 上传标注图像到 MinIO
        annotated_image_url = None
        if annotated_image_path and os.path.exists(annotated_image_path):
            try:
                if self.minio_client is None:
                    self.minio_client = MinIOClient()
                object_name = f"detection/{task.id}/{Path(annotated_image_path).name}"
                annotated_image_url = self.minio_client.upload_file(
                    object_name, annotated_image_path
                )
            except Exception as e:
                logger.error(f"上传标注图像失败: {e}")

        # 获取场景的中文类别名映射
        scene = db.query(DetectionScene).filter(DetectionScene.id == scene_id).first()
        class_names_cn_map = scene.class_names_cn if scene and scene.class_names_cn else {}

        # 保存检测结果
        for det in detections:
            class_name = det.get("class_name", "")
            result = DetectionResult(
                task_id=task.id,
                image_path=image_path,
                annotated_image_url=annotated_image_url,
                class_name=class_name,
                class_name_cn=class_names_cn_map.get(class_name, ""),
                class_id=det.get("class_id", 0),
                confidence=det.get("confidence", 0),
                bbox=det.get("bbox", []),
                image_width=det.get("image_width"),
                image_height=det.get("image_height"),
                inference_time=inference_time,
            )
            db.add(result)

        db.commit()
        db.refresh(task)

        return task

    async def save_batch_detection_results(
        self,
        db: Session,
        user_id: int,
        scene_id: int,
        task_type: str,
        batch_results: List[Dict[str, Any]],
        conf_threshold: float = 0.25,
        iou_threshold: float = 0.45,
        image_size: int = 640,
        model_version_id: Optional[int] = None,
    ) -> DetectionTask:
        """
        批量保存检测结果：创建一个 Task，多个 Results

        Args:
            db: 数据库会话
            user_id: 用户ID
            scene_id: 场景ID
            task_type: 检测类型 (batch/folder)
            batch_results: 检测结果列表，每个元素包含 image_path, detections, inference_time 等
            conf_threshold: 置信度阈值
            iou_threshold: IoU 阈值
            image_size: 推理图像尺寸
            model_version_id: 使用的模型版本ID

        Returns:
            检测任务
        """
        total_objects = sum(len(r.get("detections", [])) for r in batch_results)
        total_inference = sum(r.get("inference_time", 0) for r in batch_results)

        # 创建单个检测任务
        task = DetectionTask(
            user_id=user_id,
            scene_id=scene_id,
            task_type=task_type,
            status="completed",
            total_images=len(batch_results),
            total_objects=total_objects,
            total_inference_time=total_inference,
            conf_threshold=conf_threshold,
            iou_threshold=iou_threshold,
            image_size=image_size,
            completed_at=now_cst(),
        )
        if model_version_id:
            task.model_version_id = model_version_id
        db.add(task)
        db.flush()

        # 获取场景的中文类别名映射
        scene = db.query(DetectionScene).filter(DetectionScene.id == scene_id).first()
        class_names_cn_map = scene.class_names_cn if scene and scene.class_names_cn else {}

        # 为每张图像保存结果
        for result in batch_results:
            if "error" in result:
                continue

            image_path = result.get("image_path", "")
            inference_time = result.get("inference_time", 0)
            annotated_image_url = None

            # 上传标注图像到 MinIO
            annotated_path = result.get("annotated_image_path")
            if annotated_path and os.path.exists(annotated_path):
                try:
                    if self.minio_client is None:
                        self.minio_client = MinIOClient()
                    object_name = f"detection/{task.id}/{Path(annotated_path).name}"
                    annotated_image_url = self.minio_client.upload_file(object_name, annotated_path)
                except Exception as e:
                    logger.error(f"上传标注图像失败: {e}")

            for det in result.get("detections", []):
                class_name = det.get("class_name", "")
                det_result = DetectionResult(
                    task_id=task.id,
                    image_path=image_path,
                    annotated_image_url=annotated_image_url,
                    class_name=class_name,
                    class_name_cn=class_names_cn_map.get(class_name, ""),
                    class_id=det.get("class_id", 0),
                    confidence=det.get("confidence", 0),
                    bbox=det.get("bbox", []),
                    image_width=det.get("image_width"),
                    image_height=det.get("image_height"),
                    inference_time=inference_time,
                )
                db.add(det_result)

        db.commit()
        db.refresh(task)
        return task

    def get_task_list(
        self,
        db: Session,
        user_id: Optional[int] = None,
        scene_id: Optional[int] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Dict[str, Any]:
        """
        获取检测任务列表

        Args:
            db: 数据库会话
            user_id: 用户ID（可选）
            scene_id: 场景ID（可选）
            page: 页码
            page_size: 每页数量

        Returns:
            分页结果
        """
        query = db.query(DetectionTask)

        if user_id:
            query = query.filter(DetectionTask.user_id == user_id)
        if scene_id:
            query = query.filter(DetectionTask.scene_id == scene_id)

        total = query.count()
        tasks = (
            query.order_by(DetectionTask.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )

        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "items": [
                {
                    "id": t.id,
                    "task_type": t.task_type,
                    "status": t.status,
                    "scene_id": t.scene_id,
                    "total_images": t.total_images,
                    "total_objects": t.total_objects,
                    "conf_threshold": t.conf_threshold,
                    "iou_threshold": t.iou_threshold,
                    "created_at": t.created_at.isoformat() if t.created_at else None,
                }
                for t in tasks
            ],
        }

    def get_task_results(
        self, db: Session, task_id: int, page: int = 1, page_size: int = 50
    ) -> Dict[str, Any]:
        """
        获取检测任务结果

        Args:
            db: 数据库会话
            task_id: 任务ID
            page: 页码
            page_size: 每页数量

        Returns:
            分页结果
        """
        query = db.query(DetectionResult).filter(DetectionResult.task_id == task_id)

        total = query.count()
        results = query.offset((page - 1) * page_size).limit(page_size).all()

        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "items": [
                {
                    "id": r.id,
                    "image_path": r.image_path,
                    "annotated_image_url": r.annotated_image_url,
                    "class_name": r.class_name,
                    "class_id": r.class_id,
                    "confidence": r.confidence,
                    "bbox": r.bbox,
                    "image_width": r.image_width,
                    "image_height": r.image_height,
                    "inference_time": r.inference_time,
                }
                for r in results
            ],
        }


# 全局检测服务实例
detection_service = DetectionService()
