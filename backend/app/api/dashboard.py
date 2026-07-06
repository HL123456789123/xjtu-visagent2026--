"""
Dashboard 数据统计 API 路由
提供后端聚合的统计数据，避免前端多次请求和聚合计算
"""

from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.security import get_current_user, RequirePermission
from app.core.logger import get_logger
from app.core.tz import now_cst
from app.database.session import get_db
from app.entity.db_models import (
    User,
    DetectionTask,
    DetectionResult,
    DetectionScene,
    TrainingTask,
    Model,
    ChatSession,
)
from app.entity.schemas import ApiResponse

logger = get_logger("dashboard_api")

router = APIRouter(prefix="/api/dashboard", tags=["数据看板"])


@router.get("/stats", response_model=ApiResponse, dependencies=[Depends(RequirePermission("system:dashboard"))])
async def get_dashboard_stats(
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    """
    获取 Dashboard 统计数据

    返回：
    - 总检测次数
    - 总训练任务数
    - 总模型数量
    - 总对话次数
    - 各场景检测统计
    - 近7天检测趋势
    - 各类别检测分布
    - 训练任务状态分布
    """
    try:
        # 非管理员仅查看自己的数据
        is_admin = current_user.is_superuser
        user_filter = None if is_admin else current_user.id

        # 1. 基础统计
        det_query = db.query(func.count(DetectionTask.id))
        train_query = db.query(func.count(TrainingTask.id))
        model_query = db.query(func.count(Model.id)).filter(Model.status == "active")

        if user_filter:
            det_query = det_query.filter(DetectionTask.user_id == user_filter)
            train_query = train_query.filter(TrainingTask.user_id == user_filter)
            model_query = model_query.filter(Model.created_by == user_filter)

        total_detections = det_query.scalar() or 0
        total_training = train_query.scalar() or 0
        total_models = model_query.scalar() or 0
        total_sessions = (
            db.query(func.count(ChatSession.id))
            .filter(ChatSession.user_id == current_user.id)
            .scalar()
            or 0
        )

        # 2. 近7天检测趋势
        seven_days_ago = now_cst() - timedelta(days=7)
        trend_query = db.query(
            func.date(DetectionTask.created_at).label("date"),
            func.count(DetectionTask.id).label("count"),
        ).filter(DetectionTask.created_at >= seven_days_ago)
        if user_filter:
            trend_query = trend_query.filter(DetectionTask.user_id == user_filter)
        daily_detections = (
            trend_query.group_by(func.date(DetectionTask.created_at)).order_by("date").all()
        )

        # 填充完整7天数据
        trend_data = []
        for i in range(7):
            date = (now_cst() - timedelta(days=6 - i)).strftime("%Y-%m-%d")
            count = next((d.count for d in daily_detections if str(d.date) == date), 0)
            trend_data.append({"date": date, "count": count})

        # 3. 各场景检测统计
        scene_query = db.query(
            DetectionScene.display_name, func.count(DetectionTask.id).label("count")
        ).outerjoin(
            DetectionTask,
            (DetectionTask.scene_id == DetectionScene.id)
            & (
                (user_filter is None) | (DetectionTask.user_id == user_filter)
            ),
        )
        # 注意：将 user_filter 放入 join 条件而非 WHERE，避免 outer join 退化为 inner join
        scene_stats = scene_query.group_by(DetectionScene.id, DetectionScene.display_name).all()

        scene_data = [{"name": s.display_name, "count": s.count} for s in scene_stats]

        # 4. 各类别检测分布
        class_query = db.query(
            DetectionResult.class_name, func.count(DetectionResult.id).label("count")
        )
        if user_filter:
            class_query = class_query.join(
                DetectionTask, DetectionResult.task_id == DetectionTask.id
            ).filter(DetectionTask.user_id == user_filter)
        class_distribution = (
            class_query.group_by(DetectionResult.class_name)
            .order_by(func.count(DetectionResult.id).desc())
            .limit(10)
            .all()
        )

        class_data = [{"name": c.class_name, "count": c.count} for c in class_distribution]

        # 5. 训练任务状态分布
        status_query = db.query(TrainingTask.status, func.count(TrainingTask.id).label("count"))
        if user_filter:
            status_query = status_query.filter(TrainingTask.user_id == user_filter)
        training_status = status_query.group_by(TrainingTask.status).all()

        status_data = [{"status": s.status, "count": s.count} for s in training_status]

        # 6. 最近检测任务
        recent_query = db.query(DetectionTask)
        if user_filter:
            recent_query = recent_query.filter(DetectionTask.user_id == user_filter)
        recent_detections = recent_query.order_by(DetectionTask.created_at.desc()).limit(5).all()

        recent_data = [
            {
                "id": t.id,
                "task_type": t.task_type,
                "total_objects": t.total_objects,
                "created_at": t.created_at.isoformat() if t.created_at else None,
            }
            for t in recent_detections
        ]

        return ApiResponse(
            code=200,
            data={
                "overview": {
                    "total_detections": total_detections,
                    "total_training": total_training,
                    "total_models": total_models,
                    "total_sessions": total_sessions,
                },
                "trend": trend_data,
                "scene_stats": scene_data,
                "class_distribution": class_data,
                "training_status": status_data,
                "recent_detections": recent_data,
            },
        )

    except Exception as e:
        logger.error(f"获取统计数据失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取统计数据失败: {str(e)}")


@router.get("/user-stats", response_model=ApiResponse, dependencies=[Depends(RequirePermission("system:dashboard"))])
async def get_user_stats(
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    """获取当前用户的统计数据"""
    try:
        # 用户检测统计
        user_detections = (
            db.query(func.count(DetectionTask.id))
            .filter(DetectionTask.user_id == current_user.id)
            .scalar()
            or 0
        )

        # 用户训练统计
        user_training = (
            db.query(func.count(TrainingTask.id))
            .filter(TrainingTask.user_id == current_user.id)
            .scalar()
            or 0
        )

        # 用户对话统计
        user_sessions = (
            db.query(func.count(ChatSession.id))
            .filter(ChatSession.user_id == current_user.id)
            .scalar()
            or 0
        )

        # 用户检测目标总数
        user_objects = (
            db.query(func.sum(DetectionTask.total_objects))
            .filter(DetectionTask.user_id == current_user.id)
            .scalar()
            or 0
        )

        return ApiResponse(
            code=200,
            data={
                "detections": user_detections,
                "training_tasks": user_training,
                "chat_sessions": user_sessions,
                "total_objects": user_objects,
            },
        )

    except Exception as e:
        logger.error(f"获取用户统计数据失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取用户统计数据失败: {str(e)}")
