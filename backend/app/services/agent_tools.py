"""
Agent 工具模块
提供 LangGraph Agent 使用的各种工具
包括检测、历史查询、统计、知识库检索等
"""

import json
from contextlib import contextmanager
from typing import Optional

from langchain_core.tools import tool
from pydantic import BaseModel, Field

from app.core.logger import get_logger

logger = get_logger("agent_tools")


@contextmanager
def _agent_db():
    """Agent 工具统一的数据库会话上下文管理器"""
    from app.database.session import SessionLocal

    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


# ── 工具输入模型 ──────────────────────────────────────


class DetectObjectsInput(BaseModel):
    """检测工具输入"""

    image_path: str = Field(description="图像文件路径")
    scene_name: str = Field(description="检测场景名称，如 remote_sensing、agriculture")
    conf_threshold: float = Field(default=0.25, description="置信度阈值，范围0-1")


class QueryHistoryInput(BaseModel):
    """历史查询输入"""

    query: str = Field(description="查询条件，如最近的检测记录、某个场景的检测结果等")
    limit: int = Field(default=10, description="返回结果数量")


class GetStatisticsInput(BaseModel):
    """统计信息输入"""

    scene_name: Optional[str] = Field(default=None, description="场景名称，为空则返回所有场景统计")


class SearchKnowledgeInput(BaseModel):
    """知识库检索输入"""

    query: str = Field(description="检索查询内容")
    top_k: int = Field(default=5, description="返回结果数量")


# ── 工具函数 ──────────────────────────────────────────


@tool("detect_objects", args_schema=DetectObjectsInput)
async def detect_objects(image_path: str, scene_name: str, conf_threshold: float = 0.25) -> str:
    """
    执行目标检测，识别图像中的物体。
    使用此工具可以检测遥感图像、工业缺陷、农业病害等场景中的目标。

    Args:
        image_path: 图像文件路径
        scene_name: 检测场景名称
        conf_threshold: 置信度阈值

    Returns:
        检测结果JSON字符串
    """
    try:
        from app.entity.db_models import DetectionScene
        from app.services.detection_service import detection_service

        with _agent_db() as db:
            # 查找场景
            scene = db.query(DetectionScene).filter(DetectionScene.name == scene_name).first()

            if not scene:
                return json.dumps(
                    {
                        "error": f"场景 '{scene_name}' 不存在",
                        "available_scenes": "请使用 get_scenes 工具查看可用场景",
                    }
                )

            # 执行检测
            result = await detection_service.detect_single(
                db=db, scene_id=scene.id, image_path=image_path, conf_threshold=conf_threshold
            )

            # 格式化结果
            formatted_result = {
                "scene": scene.display_name,
                "total_objects": result["total_objects"],
                "inference_time_ms": round(result["inference_time"], 2),
                "detections": [],
            }

            for det in result["detections"]:
                formatted_result["detections"].append(
                    {
                        "class": det["class_name"],
                        "confidence": round(det["confidence"], 3),
                        "bbox": [round(x, 1) for x in det["bbox"]],
                    }
                )

            return json.dumps(formatted_result, ensure_ascii=False)

    except Exception as e:
        logger.error(f"检测工具执行失败: {e}")
        return json.dumps({"error": str(e)})


@tool("query_history", args_schema=QueryHistoryInput)
async def query_history(query: str, limit: int = 10) -> str:
    """
    查询检测历史记录。
    可以查询最近的检测记录、某个场景的检测结果等。

    Args:
        query: 查询条件
        limit: 返回结果数量

    Returns:
        历史记录JSON字符串
    """
    try:
        from app.entity.db_models import DetectionTask, DetectionScene

        with _agent_db() as db:
            # 批量查询避免 N+1
            tasks = (
                db.query(DetectionTask).order_by(DetectionTask.created_at.desc()).limit(limit).all()
            )

            # 预加载所有相关场景
            scene_ids = list({t.scene_id for t in tasks})
            scenes = (
                db.query(DetectionScene).filter(DetectionScene.id.in_(scene_ids)).all()
                if scene_ids
                else []
            )
            scene_map = {s.id: s.display_name for s in scenes}

            results = []
            for task in tasks:
                results.append(
                    {
                        "task_id": task.id,
                        "scene": scene_map.get(task.scene_id, "未知"),
                        "task_type": task.task_type,
                        "total_objects": task.total_objects,
                        "status": task.status,
                        "created_at": task.created_at.isoformat() if task.created_at else None,
                    }
                )

            return json.dumps(
                {"query": query, "total": len(results), "records": results}, ensure_ascii=False
            )

    except Exception as e:
        logger.error(f"历史查询工具执行失败: {e}")
        return json.dumps({"error": str(e)})


@tool("get_statistics", args_schema=GetStatisticsInput)
async def get_statistics(scene_name: Optional[str] = None) -> str:
    """
    获取检测统计信息。
    可以获取某个场景或所有场景的检测统计数据。

    Args:
        scene_name: 场景名称，为空则返回所有场景统计

    Returns:
        统计信息JSON字符串
    """
    try:
        from app.entity.db_models import DetectionTask, DetectionScene
        from sqlalchemy import func

        with _agent_db() as db:
            stats = {}

            if scene_name:
                # 查询指定场景统计
                scene = db.query(DetectionScene).filter(DetectionScene.name == scene_name).first()

                if not scene:
                    return json.dumps({"error": f"场景 '{scene_name}' 不存在"})

                total_tasks = (
                    db.query(DetectionTask).filter(DetectionTask.scene_id == scene.id).count()
                )

                total_objects = (
                    db.query(func.sum(DetectionTask.total_objects))
                    .filter(DetectionTask.scene_id == scene.id)
                    .scalar()
                    or 0
                )

                stats = {
                    "scene": scene.display_name,
                    "total_tasks": total_tasks,
                    "total_objects": total_objects,
                    "class_names": scene.class_names,
                }
            else:
                # 查询所有场景统计
                scenes = db.query(DetectionScene).filter(DetectionScene.is_active.is_(True)).all()

                scene_stats = []
                for scene in scenes:
                    total_tasks = (
                        db.query(DetectionTask).filter(DetectionTask.scene_id == scene.id).count()
                    )

                    total_objects = (
                        db.query(func.sum(DetectionTask.total_objects))
                        .filter(DetectionTask.scene_id == scene.id)
                        .scalar()
                        or 0
                    )

                    scene_stats.append(
                        {
                            "scene": scene.display_name,
                            "total_tasks": total_tasks,
                            "total_objects": total_objects,
                        }
                    )

                stats = {"total_scenes": len(scenes), "scenes": scene_stats}

            return json.dumps(stats, ensure_ascii=False)

    except Exception as e:
        logger.error(f"统计工具执行失败: {e}")
        return json.dumps({"error": str(e)})


@tool("search_knowledge", args_schema=SearchKnowledgeInput)
async def search_knowledge(query: str, top_k: int = 5) -> str:
    """
    从知识库中检索相关信息。
    可以检索目标检测、模型训练、数据处理等相关的知识文档。

    Args:
        query: 检索查询内容
        top_k: 返回结果数量

    Returns:
        检索结果JSON字符串
    """
    try:
        from app.services.knowledge_service import knowledge_service

        # 执行检索
        results = await knowledge_service.search(query, k=top_k)

        return json.dumps(
            {"query": query, "total": len(results), "results": results}, ensure_ascii=False
        )

    except Exception as e:
        logger.error(f"知识库检索工具执行失败: {e}")
        return json.dumps({"query": query, "error": str(e), "results": []})


@tool("get_scenes")
async def get_scenes() -> str:
    """
    获取所有可用的检测场景。
    用于查看系统中配置的检测场景列表。

    Returns:
        场景列表JSON字符串
    """
    try:
        from app.entity.db_models import DetectionScene

        with _agent_db() as db:
            scenes = db.query(DetectionScene).filter(DetectionScene.is_active.is_(True)).all()

            result = []
            for scene in scenes:
                result.append(
                    {
                        "name": scene.name,
                        "display_name": scene.display_name,
                        "description": scene.description,
                        "category": scene.category,
                        "class_names": scene.class_names,
                    }
                )

            return json.dumps({"total": len(result), "scenes": result}, ensure_ascii=False)

    except Exception as e:
        logger.error(f"获取场景工具执行失败: {e}")
        return json.dumps({"error": str(e)})


# ── 工具列表 ──────────────────────────────────────────


def get_all_tools():
    """获取所有工具"""
    return [detect_objects, query_history, get_statistics, search_knowledge, get_scenes]
