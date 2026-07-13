"""
模型管理服务模块
提供 Model 实体的完整 CRUD、版本管理、导入导出等功能
"""

import json
import os
import shutil
import tempfile
import zipfile
from pathlib import Path
from typing import Dict, List, Optional, Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.logger import get_logger
from app.core.tz import now_cst
from app.entity.db_models import Model, ModelVersion, SceneModel, DetectionScene

logger = get_logger("model_service")

# ZIP 炸弹防护：解压总大小上限（2GB）
_MAX_UNZIP_SIZE = 2 * 1024 * 1024 * 1024


class ModelService:
    """模型管理服务类"""

    # ── 模型 CRUD ────────────────────────────────────────

    def get_model_list(
        self,
        db: Session,
        user_id: Optional[int] = None,
        category: Optional[str] = None,
        status: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Dict[str, Any]:
        """分页查询模型列表，带版本数量和场景数量统计"""
        query = db.query(Model)

        if user_id:
            query = query.filter(Model.created_by == user_id)
        if category:
            query = query.filter(Model.category == category)
        if status:
            if status == "enabled":
                query = query.filter(Model.status == "active", Model.is_enabled.is_(True))
            elif status == "disabled":
                query = query.filter(Model.status == "active", Model.is_enabled.is_(False))
            else:
                query = query.filter(Model.status == status)
        else:
            query = query.filter(Model.status == "active")

        total = query.count()
        models = (
            query.order_by(Model.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )

        items = []
        if not models:
            return {"total": total, "page": page, "page_size": page_size, "items": items}

        # 批量查询版本数量、场景数量、默认版本，避免 N+1 查询
        model_ids = [m.id for m in models]

        # 批量查询活跃版本数量
        version_counts = dict(
            db.query(ModelVersion.model_id, func.count(ModelVersion.id))
            .filter(ModelVersion.model_id.in_(model_ids), ModelVersion.status == "active")
            .group_by(ModelVersion.model_id)
            .all()
        )

        # 批量查询场景绑定数量
        scene_counts = dict(
            db.query(SceneModel.model_id, func.count(SceneModel.id))
            .filter(SceneModel.model_id.in_(model_ids))
            .group_by(SceneModel.model_id)
            .all()
        )

        # 批量查询场景名称（用于前端显示）
        model_scenes = db.query(
            SceneModel.model_id,
            DetectionScene.id,
            DetectionScene.display_name
        ).join(
            DetectionScene, SceneModel.scene_id == DetectionScene.id
        ).filter(
            SceneModel.model_id.in_(model_ids)
        ).all()

        # 按 model_id 分组场景名称
        scene_names_map = {}
        for row in model_scenes:
            model_id = row[0]
            scene_name = row[2]
            if model_id not in scene_names_map:
                scene_names_map[model_id] = []
            scene_names_map[model_id].append(scene_name)

        # 批量查询默认版本
        default_versions = dict(
            db.query(ModelVersion.model_id, ModelVersion.version)
            .filter(
                ModelVersion.model_id.in_(model_ids),
                ModelVersion.is_default.is_(True),
                ModelVersion.status == "active",
            )
            .all()
        )

        for m in models:
            items.append(
                {
                    "id": m.id,
                    "name": m.name,
                    "description": m.description,
                    "base_architecture": m.base_architecture,
                    "category": m.category,
                    "class_names": m.class_names,
                    "class_names_cn": m.class_names_cn,
                    "status": m.status,
                    "is_enabled": m.is_enabled,
                    "version_count": version_counts.get(m.id, 0),
                    "scene_count": scene_counts.get(m.id, 0),
                    "scene_names": scene_names_map.get(m.id, []),
                    "default_version": default_versions.get(m.id),
                    "created_by": m.created_by,
                    "created_at": m.created_at.isoformat() if m.created_at else None,
                    "updated_at": m.updated_at.isoformat() if m.updated_at else None,
                }
            )

        return {"total": total, "page": page, "page_size": page_size, "items": items}

    def get_model_detail(self, db: Session, model_id: int) -> Optional[Dict[str, Any]]:
        """模型详情，含版本列表和关联场景列表"""
        model = db.query(Model).filter(Model.id == model_id).first()
        if not model:
            return None

        # 版本列表
        versions = (
            db.query(ModelVersion)
            .filter(ModelVersion.model_id == model_id, ModelVersion.status == "active")
            .order_by(ModelVersion.created_at.desc())
            .all()
        )

        version_list = [
            {
                "id": v.id,
                "version": v.version,
                "source": v.source,
                "status": v.status,
                "model_path": v.model_path,
                "file_size": v.file_size,
                "is_default": v.is_default,
                "map50": v.map50,
                "map50_95": v.map50_95,
                "precision": v.precision,
                "recall": v.recall,
                "description": v.description,
                "created_at": v.created_at.isoformat() if v.created_at else None,
            }
            for v in versions
        ]

        # 关联场景列表（批量查询避免 N+1）
        scene_models = db.query(SceneModel).filter(SceneModel.model_id == model_id).all()
        scene_list = []
        if scene_models:
            scene_ids = [sm.scene_id for sm in scene_models]
            # 使用字典推导式正确构建场景映射
            scene_data = db.query(DetectionScene).filter(DetectionScene.id.in_(scene_ids)).all()
            scenes = {s.id: s for s in scene_data}
            for sm in scene_models:
                scene = scenes.get(sm.scene_id)
                if scene:
                    scene_list.append(
                        {
                            "scene_id": scene.id,
                            "scene_name": scene.display_name,
                            "category": scene.category,
                            "is_default": sm.is_default,
                        }
                    )

        return {
            "id": model.id,
            "name": model.name,
            "description": model.description,
            "base_architecture": model.base_architecture,
            "category": model.category,
            "class_names": model.class_names,
            "class_names_cn": model.class_names_cn,
            "status": model.status,
            "is_enabled": model.is_enabled,
            "created_by": model.created_by,
            "created_at": model.created_at.isoformat() if model.created_at else None,
            "updated_at": model.updated_at.isoformat() if model.updated_at else None,
            "versions": version_list,
            "scenes": scene_list,
        }

    def create_model(
        self,
        db: Session,
        user_id: int,
        name: str,
        description: Optional[str] = None,
        base_architecture: str = "yolo26n",
        category: str = "general",
        class_names: Optional[list] = None,
        class_names_cn: Optional[dict] = None,
        scene_id: Optional[int] = None,
    ) -> Model:
        """创建模型，可选绑定到检测场景"""
        # 检查名称唯一性
        existing = db.query(Model).filter(Model.name == name).first()
        if existing:
            raise ValueError(f"模型名称已存在: {name}")

        model = Model(
            name=name,
            description=description,
            base_architecture=base_architecture,
            category=category,
            class_names=class_names or [],
            class_names_cn=class_names_cn,
            status="active",
            created_by=user_id,
        )
        db.add(model)
        db.flush()  # 获取 model.id

        # 如果指定了场景，绑定模型到场景
        if scene_id:
            scene = db.query(DetectionScene).filter(DetectionScene.id == scene_id).first()
            if scene:
                scene_model = SceneModel(
                    scene_id=scene_id,
                    model_id=model.id,
                    is_default=False,
                )
                db.add(scene_model)
                logger.info(f"绑定模型到场景: model_id={model.id}, scene_id={scene_id}")

        db.commit()
        db.refresh(model)
        logger.info(f"创建模型: id={model.id}, name={name}")
        return model

    def upload_weight_file(
        self,
        db: Session,
        model_id: int,
        file_path: str,
        original_filename: str,
    ) -> Optional[ModelVersion]:
        """
        上传权重文件并创建模型版本

        Args:
            db: 数据库会话
            model_id: 目标模型ID
            file_path: 临时文件路径
            original_filename: 原始文件名

        Returns:
            创建的 ModelVersion，失败返回 None
        """
        from pathlib import Path
        import shutil

        model = db.query(Model).filter(Model.id == model_id).first()
        if not model:
            return None

        try:
            # 创建存储目录
            models_dir = Path("data/models") / model.name
            models_dir.mkdir(parents=True, exist_ok=True)

            # 生成版本号（使用时间戳）
            from app.core.tz import now_cst
            timestamp = now_cst().strftime("%Y%m%d%H%M%S")
            version_str = f"v1.0.0-{timestamp}"

            # 复制文件到目标位置
            dest_path = models_dir / f"{model.name}_{version_str}.pt"
            shutil.copy2(file_path, dest_path)

            file_size = dest_path.stat().st_size

            # 检查是否是第一个版本
            version_count = (
                db.query(ModelVersion).filter(ModelVersion.model_id == model_id).count()
            )

            # 创建版本记录
            mv = ModelVersion(
                model_id=model_id,
                version=version_str,
                source="upload",
                status="active",
                model_path=str(dest_path),
                file_size=file_size,
                description=f"上传自 {original_filename}",
                is_default=(version_count == 0),  # 第一个版本设为默认
            )
            db.add(mv)
            db.commit()
            db.refresh(mv)

            logger.info(f"上传权重文件: model_id={model_id}, version={version_str}, path={dest_path}")
            return mv

        except Exception as e:
            logger.error(f"上传权重文件失败: {e}")
            db.rollback()
            return None

    def update_model(self, db: Session, model_id: int, **kwargs) -> Optional[Model]:
        """更新模型信息"""
        model = db.query(Model).filter(Model.id == model_id).first()
        if not model:
            return None

        allowed_fields = {
            "name",
            "description",
            "base_architecture",
            "category",
            "class_names",
            "class_names_cn",
            "status",
        }
        # 允许将 description 等可选字段设为 None（清空）
        for key, value in kwargs.items():
            if key in allowed_fields:
                setattr(model, key, value)

        model.updated_at = now_cst()
        db.commit()
        db.refresh(model)
        logger.info(f"更新模型: id={model_id}")
        return model

    def toggle_model_enabled(self, db: Session, model_id: int) -> Optional[Model]:
        """切换模型启用/禁用状态"""
        model = db.query(Model).filter(Model.id == model_id).first()
        if not model:
            return None

        model.is_enabled = not model.is_enabled
        model.updated_at = now_cst()
        db.commit()
        db.refresh(model)
        status_text = "启用" if model.is_enabled else "禁用"
        logger.info(f"{status_text}模型: id={model_id}, name={model.name}")
        return model

    def delete_model(self, db: Session, model_id: int) -> bool:
        """归档模型（软删除）"""
        model = db.query(Model).filter(Model.id == model_id).first()
        if not model:
            return False

        model.status = "archived"
        model.updated_at = now_cst()
        # 同时归档所有版本
        db.query(ModelVersion).filter(
            ModelVersion.model_id == model_id, ModelVersion.status == "active"
        ).update({"status": "archived"})

        db.commit()
        logger.info(f"归档模型: id={model_id}, name={model.name}")
        return True

    # ── 版本管理 ──────────────────────────────────────────

    def get_model_versions(
        self, db: Session, model_id: int, page: int = 1, page_size: int = 20
    ) -> Dict[str, Any]:
        """获取某模型的版本列表"""
        query = db.query(ModelVersion).filter(
            ModelVersion.model_id == model_id,
            ModelVersion.status == "active",
        )
        total = query.count()
        versions = (
            query.order_by(ModelVersion.created_at.desc())
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
                    "id": v.id,
                    "version": v.version,
                    "source": v.source,
                    "model_path": v.model_path,
                    "file_size": v.file_size,
                    "is_default": v.is_default,
                    "map50": v.map50,
                    "map50_95": v.map50_95,
                    "precision": v.precision,
                    "recall": v.recall,
                    "description": v.description,
                    "created_at": v.created_at.isoformat() if v.created_at else None,
                }
                for v in versions
            ],
        }

    def set_default_version(self, db: Session, model_id: int, version_id: int) -> bool:
        """设置模型默认版本"""
        version = (
            db.query(ModelVersion)
            .filter(
                ModelVersion.id == version_id,
                ModelVersion.model_id == model_id,
                ModelVersion.status == "active",
            )
            .first()
        )
        if not version:
            return False

        # 取消其他默认版本
        db.query(ModelVersion).filter(
            ModelVersion.model_id == model_id, ModelVersion.is_default.is_(True)
        ).update({"is_default": False})

        version.is_default = True
        db.commit()
        logger.info(f"设置默认版本: model_id={model_id}, version_id={version_id}")
        return True

    def delete_model_version(self, db: Session, version_id: int) -> bool:
        """归档模型版本"""
        version = db.query(ModelVersion).filter(ModelVersion.id == version_id).first()
        if not version:
            return False

        version.status = "archived"
        db.commit()
        logger.info(f"归档模型版本: id={version_id}, version={version.version}")
        return True

    # ── 导入导出 ──────────────────────────────────────────

    def export_model(self, db: Session, model_id: int, version_id: int) -> Optional[str]:
        """
        导出模型 ZIP 包

        ZIP 结构：
        ├── manifest.json      — 元信息
        ├── weights/best.pt    — 权重文件
        └── config/model.json  — 模型配置

        Returns:
            ZIP 文件路径，失败返回 None
        """
        model = db.query(Model).filter(Model.id == model_id).first()
        version = (
            db.query(ModelVersion)
            .filter(ModelVersion.id == version_id, ModelVersion.model_id == model_id)
            .first()
        )
        if not model or not version:
            return None

        if version.status != "active":
            logger.warning(f"无法导出已归档的版本: version_id={version_id}, status={version.status}")
            return None

        if not os.path.exists(version.model_path):
            logger.error(f"模型文件不存在: {version.model_path}")
            return None

        try:
            tmp_dir = tempfile.mkdtemp(prefix="model_export_")
            zip_path = os.path.join(tmp_dir, f"{model.name}_{version.version}.zip")

            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
                # manifest.json
                manifest = {
                    "model_name": model.name,
                    "version": version.version,
                    "base_architecture": model.base_architecture,
                    "category": model.category,
                    "class_names": model.class_names,
                    "class_names_cn": model.class_names_cn,
                    "source": version.source,
                    "exported_at": now_cst().isoformat(),
                    "metrics": {
                        "map50": version.map50,
                        "map50_95": version.map50_95,
                        "precision": version.precision,
                        "recall": version.recall,
                    },
                }
                zf.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))

                # weights/best.pt
                zf.write(version.model_path, "weights/best.pt")

                # config/model.json
                config = {
                    "base_architecture": model.base_architecture,
                    "class_names": model.class_names,
                    "class_names_cn": model.class_names_cn,
                }
                zf.writestr("config/model.json", json.dumps(config, ensure_ascii=False, indent=2))

            logger.info(f"导出模型: {zip_path}")
            return zip_path

        except Exception as e:
            logger.error(f"导出模型失败: {e}")
            # 清理失败的临时目录
            if 'tmp_dir' in locals() and os.path.exists(tmp_dir):
                shutil.rmtree(tmp_dir, ignore_errors=True)
            return None

    def import_model(
        self,
        db: Session,
        model_id: int,
        zip_path: str,
        description: Optional[str] = None,
    ) -> Optional[ModelVersion]:
        """
        从 ZIP 导入模型版本，同步更新模型元信息

        ZIP 结构：
        ├── manifest.json      — 元信息
        ├── weights/best.pt    — 权重文件
        └── config/model.json  — 模型配置

        Args:
            db: 数据库会话
            model_id: 目标模型ID
            zip_path: ZIP 文件路径
            description: 版本描述

        Returns:
            创建的 ModelVersion，失败返回 None
        """
        model = db.query(Model).filter(Model.id == model_id).first()
        if not model:
            return None

        try:
            with zipfile.ZipFile(zip_path, "r") as zf:
                # 验证 ZIP 结构
                names = zf.namelist()
                if "weights/best.pt" not in names:
                    logger.error("ZIP 中缺少 weights/best.pt")
                    return None

                # ZIP 炸弹防护：检查解压总大小
                total_size = sum(info.file_size for info in zf.infolist())
                if total_size > _MAX_UNZIP_SIZE:
                    logger.error(
                        f"ZIP 炸弹防护：解压总大小 {total_size} 超过上限 {_MAX_UNZIP_SIZE}"
                    )
                    return None

                # 创建存储目录
                models_dir = Path("data/models") / model.name
                models_dir.mkdir(parents=True, exist_ok=True)

                # 读取 manifest
                manifest = {}
                version_str = "v1.0.0"
                if "manifest.json" in names:
                    manifest = json.loads(zf.read("manifest.json"))
                    version_str = manifest.get("version", version_str)

                # 检查版本是否已存在
                existing = (
                    db.query(ModelVersion)
                    .filter(
                        ModelVersion.model_id == model_id,
                        ModelVersion.version == version_str,
                    )
                    .first()
                )
                if existing:
                    logger.warning(f"版本已存在: {version_str}")
                    return None

                # 解压权重文件
                dest_path = models_dir / f"{model.name}_{version_str}.pt"
                with zf.open("weights/best.pt") as src, open(dest_path, "wb") as dst:
                    shutil.copyfileobj(src, dst)

                file_size = dest_path.stat().st_size

                # 同步更新模型元信息（如果 manifest 中包含）
                if manifest:
                    if "base_architecture" in manifest:
                        model.base_architecture = manifest["base_architecture"]
                    if "category" in manifest:
                        model.category = manifest["category"]
                    if "class_names" in manifest:
                        model.class_names = manifest["class_names"]
                    if "class_names_cn" in manifest:
                        model.class_names_cn = manifest["class_names_cn"]
                    model.updated_at = now_cst()
                    logger.info(f"更新模型元信息: model_id={model_id}")

                # 检查是否有版本数量
                version_count = (
                    db.query(ModelVersion).filter(ModelVersion.model_id == model_id).count()
                )

                # 创建版本记录
                mv = ModelVersion(
                    model_id=model_id,
                    version=version_str,
                    source="import",
                    status="active",
                    model_path=str(dest_path),
                    file_size=file_size,
                    description=description
                    or f"导入于 {now_cst().strftime('%Y-%m-%d %H:%M')}",
                    is_default=(version_count == 0),
                    # 导入评估指标（如果存在）
                    map50=manifest.get("metrics", {}).get("map50"),
                    map50_95=manifest.get("metrics", {}).get("map50_95"),
                    precision=manifest.get("metrics", {}).get("precision"),
                    recall=manifest.get("metrics", {}).get("recall"),
                )
                db.add(mv)
                db.commit()
                db.refresh(mv)

                logger.info(f"导入模型版本: model_id={model_id}, version={version_str}")
                return mv

        except Exception as e:
            logger.error(f"导入模型失败: {e}")
            db.rollback()
            return None

    # ── 场景绑定 ──────────────────────────────────────────

    def get_scene_models(self, db: Session, scene_id: int) -> List[Dict[str, Any]]:
        """获取场景关联的模型列表（含版本信息）— 批量查询避免 N+1，仅返回已启用模型"""
        scene_models = db.query(SceneModel).filter(SceneModel.scene_id == scene_id).all()
        if not scene_models:
            return []

        # 批量查询所有关联的 Model（仅已启用且未归档）
        model_ids = [sm.model_id for sm in scene_models]
        models = {
            m.id: m
            for m in db.query(Model)
            .filter(Model.id.in_(model_ids), Model.status == "active", Model.is_enabled.is_(True))
            .all()
        }

        # 批量查询所有 ModelVersion，按 model_id 分组
        all_versions = (
            db.query(ModelVersion)
            .filter(ModelVersion.model_id.in_(model_ids), ModelVersion.status == "active")
            .order_by(ModelVersion.created_at.desc())
            .all()
        )
        versions_by_model: Dict[int, list] = {}
        for v in all_versions:
            versions_by_model.setdefault(v.model_id, []).append(v)

        # 组装结果
        result = []
        for sm in scene_models:
            model = models.get(sm.model_id)
            if not model:
                continue
            version_list = [
                {
                    "id": v.id,
                    "version": v.version,
                    "source": v.source,
                    "is_default": v.is_default,
                    "status": v.status,
                    "map50": v.map50,
                    "map50_95": v.map50_95,
                }
                for v in versions_by_model.get(model.id, [])
            ]
            # 获取默认版本ID
            default_version = next(
                (v for v in versions_by_model.get(model.id, []) if v.is_default), None
            )
            default_version_id = default_version.id if default_version else None
            result.append(
                {
                    "scene_model_id": sm.id,
                    "model_id": model.id,
                    "model_name": model.name,
                    "base_architecture": model.base_architecture,
                    "category": model.category,
                    "is_default": sm.is_default,
                    "default_version_id": default_version_id,
                    "versions": version_list,
                }
            )
        return result

    def bind_model_to_scene(
        self, db: Session, scene_id: int, model_id: int, is_default: bool = False
    ) -> Optional[SceneModel]:
        """绑定模型到场景"""
        # 检查是否已绑定
        existing = (
            db.query(SceneModel)
            .filter(SceneModel.scene_id == scene_id, SceneModel.model_id == model_id)
            .first()
        )
        if existing:
            return existing

        if is_default:
            # 取消其他默认
            db.query(SceneModel).filter(
                SceneModel.scene_id == scene_id, SceneModel.is_default.is_(True)
            ).update({"is_default": False})

        sm = SceneModel(scene_id=scene_id, model_id=model_id, is_default=is_default)
        db.add(sm)
        db.commit()
        db.refresh(sm)
        logger.info(f"绑定模型到场景: scene_id={scene_id}, model_id={model_id}")
        return sm

    def unbind_model_from_scene(self, db: Session, scene_id: int, model_id: int) -> bool:
        """解绑模型与场景"""
        sm = (
            db.query(SceneModel)
            .filter(SceneModel.scene_id == scene_id, SceneModel.model_id == model_id)
            .first()
        )
        if not sm:
            return False

        db.delete(sm)
        db.commit()
        logger.info(f"解绑模型: scene_id={scene_id}, model_id={model_id}")
        return True


# 全局模型管理服务实例
model_service = ModelService()
