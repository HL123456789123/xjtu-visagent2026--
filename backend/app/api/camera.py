"""
摄像头实时检测 API 路由
提供 WebSocket 接口接收视频帧并返回检测结果
"""

import asyncio
import time
from typing import Optional

import cv2
import numpy as np
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from sqlalchemy.orm import Session

from app.core.logger import get_logger
from app.core.security import decode_access_token, get_current_user, RequirePermission, is_super_admin
from app.entity.schemas import ApiResponse
from app.database.session import get_db, SessionLocal
from app.entity.db_models import User, DetectionScene, ModelVersion, SceneModel, UserRole, RolePermission, Permission
from app.services.detection_service import detection_service
from app.services.user_service import user_service

logger = get_logger("camera_api")

router = APIRouter(prefix="/api/camera", tags=["摄像头检测"])


class CameraSession:
    """摄像头会话管理"""

    def __init__(self, websocket: WebSocket, scene_id: int, user_id: int):
        self.websocket = websocket
        self.scene_id = scene_id
        self.user_id = user_id
        self.is_active = False
        self.frame_count = 0
        self.start_time = time.time()

    async def send_json(self, data: dict):
        """发送 JSON 数据"""
        await self.websocket.send_json(data)

    async def receive_frame(self) -> Optional[bytes]:
        """接收一帧图像"""
        try:
            data = await self.websocket.receive_bytes()
            return data
        except Exception:
            return None

    def get_fps(self) -> float:
        """计算 FPS"""
        elapsed = time.time() - self.start_time
        if elapsed == 0:
            return 0
        return self.frame_count / elapsed


def _authenticate_websocket_token(token: Optional[str]) -> Optional[int]:
    """验证 WebSocket 连接的 JWT Token，返回 user_id 或 None"""
    if not token:
        return None
    try:
        payload = decode_access_token(token)
        user_id_str = payload.get("sub")
        if user_id_str is None:
            return None
        return int(user_id_str)
    except Exception:
        return None


def _check_websocket_permission(db, user_id: int, permission_code: str) -> bool:
    """检查 WebSocket 用户是否拥有指定权限"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return False
    if is_super_admin(user, db):
        return True
    has_perm = (
        db.query(Permission)
        .join(RolePermission, RolePermission.permission_id == Permission.id)
        .join(UserRole, UserRole.role_id == RolePermission.role_id)
        .filter(UserRole.user_id == user_id, Permission.code == permission_code)
        .first()
    )
    return has_perm is not None


@router.websocket("/detect")
async def camera_detect(
    websocket: WebSocket,
    scene_id: int,
    token: Optional[str] = None,
    conf_threshold: float = 0.25,
    iou_threshold: float = 0.45,
):
    """
    摄像头实时检测 WebSocket 端点

    参数：
    - scene_id: 检测场景 ID
    - token: JWT Token（用于身份验证，必传）

    协议：
    - 客户端发送：二进制图像帧（JPEG/PNG）
    - 服务端返回：JSON 格式检测结果

    返回格式：
    {
        "type": "detection",
        "detections": [...],
        "total_objects": int,
        "inference_time": float,
        "fps": float
    }
    """
    # JWT 身份验证
    user_id = _authenticate_websocket_token(token)
    if user_id is None:
        await websocket.close(code=4001, reason="认证失败，请提供有效的 JWT Token")
        return

    # 验证用户是否存在且活跃
    db = None
    try:
        db = SessionLocal()
        user = user_service.get_user_by_id(db, user_id)
        if not user or not user.is_active:
            await websocket.close(code=4001, reason="用户不存在或已被禁用")
            return
        # 检查检测权限
        if not _check_websocket_permission(db, user_id, "detection:task:create"):
            await websocket.close(code=4003, reason="权限不足，需要 detection:task:create 权限")
            return
    except Exception:
        await websocket.close(code=4001, reason="认证失败")
        return

    await websocket.accept()
    logger.info(f"摄像头连接建立: scene_id={scene_id}, user_id={user_id}")

    session = None
    try:
        scene = (
            db.query(DetectionScene)
            .filter(DetectionScene.id == scene_id, DetectionScene.is_active.is_(True))
            .first()
        )

        if not scene:
            await websocket.send_json({"type": "error", "message": f"场景 {scene_id} 不存在"})
            await websocket.close()
            return

        # 获取默认模型（通过 SceneModel 关联表查找）
        scene_model = (
            db.query(SceneModel)
            .filter(SceneModel.scene_id == scene_id, SceneModel.is_default.is_(True))
            .first()
        )

        model_path = "yolo26n.pt"
        if scene_model:
            model_version = (
                db.query(ModelVersion)
                .filter(
                    ModelVersion.model_id == scene_model.model_id,
                    ModelVersion.is_default.is_(True),
                    ModelVersion.status == "active",
                )
                .first()
            )
            if model_version:
                model_path = model_version.model_path

        # 加载模型
        cache_key = (scene_id, None)
        if not detection_service.load_model(scene_id, model_path, cache_key=cache_key):
            await websocket.send_json({"type": "error", "message": "模型加载失败"})
            await websocket.close()
            return

        # 创建会话
        session = CameraSession(websocket, scene_id, user_id)
        session.is_active = True

        # 发送连接成功消息
        await session.send_json(
            {"type": "connected", "scene": scene.display_name, "model": model_path}
        )

        # 主循环：接收帧并检测（带背压丢帧控制）
        frame_queue: asyncio.Queue = asyncio.Queue(maxsize=1)

        async def receive_frames():
            """独立接收帧任务，队列满时丢弃旧帧"""
            try:
                while True:
                    data = await session.receive_frame()
                    if data is None:
                        await frame_queue.put(None)  # 结束信号
                        break
                    if frame_queue.full():
                        try:
                            frame_queue.get_nowait()  # 丢弃旧帧
                        except asyncio.QueueEmpty:
                            pass
                    await frame_queue.put(data)
            except Exception:
                await frame_queue.put(None)

        # 启动帧接收任务
        recv_task = asyncio.create_task(receive_frames())

        try:
            while session.is_active:
                # 等待最新帧
                frame_data = await frame_queue.get()
                if frame_data is None:
                    break

                session.frame_count += 1

                try:
                    # 解码图像
                    nparr = np.frombuffer(frame_data, np.uint8)
                    frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

                    if frame is None:
                        await session.send_json({"type": "error", "message": "图像解码失败"})
                        continue

                    # 执行检测（通过 to_thread 避免阻塞事件循环）
                    start_time = time.time()
                    results = await asyncio.to_thread(
                        detection_service.models[cache_key],
                        frame, conf=conf_threshold, iou=iou_threshold,
                    )
                    inference_time = (time.time() - start_time) * 1000  # ms

                    # 解析检测结果
                    detections = []
                    if results and len(results) > 0:
                        result = results[0]
                        if result.boxes is not None:
                            for box in result.boxes:
                                x1, y1, x2, y2 = box.xyxy[0].tolist()
                                conf = float(box.conf[0])
                                cls_id = int(box.cls[0])
                                cls_name = result.names[cls_id]

                                detections.append(
                                    {
                                        "bbox": [x1, y1, x2, y2],
                                        "confidence": conf,
                                        "class_id": cls_id,
                                        "class_name": cls_name,
                                    }
                                )

                    # 发送检测结果
                    await session.send_json(
                        {
                            "type": "detection",
                            "detections": detections,
                            "total_objects": len(detections),
                            "inference_time": round(inference_time, 2),
                            "fps": round(session.get_fps(), 1),
                            "frame_id": session.frame_count,
                        }
                    )

                except Exception as e:
                    logger.error(f"帧处理失败: {e}")
                    await session.send_json({"type": "error", "message": f"处理失败: {str(e)}"})

        finally:
            recv_task.cancel()
            try:
                await recv_task
            except asyncio.CancelledError:
                pass

    except WebSocketDisconnect:
        logger.info(f"摄像头连接断开: scene_id={scene_id}")
    except Exception as e:
        logger.error(f"摄像头检测错误: {e}")
        try:
            await websocket.send_json({"type": "error", "message": str(e)})
        except Exception:
            pass
    finally:
        if db is not None:
            db.close()
        frame_count = session.frame_count if session is not None else 0
        logger.info(
            f"摄像头会话结束: scene_id={scene_id}, frames={frame_count}"
        )


@router.get("/scenes", response_model=ApiResponse, dependencies=[Depends(RequirePermission("detection:task:view"))])
async def get_camera_scenes(
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    """获取支持摄像头检测的场景列表"""
    scenes = db.query(DetectionScene).filter(DetectionScene.is_active.is_(True)).all()

    return ApiResponse(
        code=200,
        data=[
            {"id": s.id, "name": s.name, "display_name": s.display_name, "category": s.category}
            for s in scenes
        ],
    )
