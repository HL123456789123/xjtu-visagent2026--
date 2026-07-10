"""
训练服务模块
提供 YOLO26 模型训练的完整业务逻辑
包括创建训练任务、启动/暂停/取消训练、获取训练状态和指标
"""

import csv
import os
import threading
from typing import Dict, List, Optional, Any

from sqlalchemy.orm import Session

from app.core.logger import get_logger
from app.core.tz import now_cst
from app.storage.redis_client import redis_client
from app.entity.db_models import TrainingTask, TrainingMetric, ModelVersion

logger = get_logger("training_service")


class TrainingService:
    """训练服务类"""

    def __init__(self):
        self.active_tasks: Dict[int, threading.Thread] = {}
        self.task_stop_flags: Dict[int, threading.Event] = {}
        self._lock = threading.Lock()
        # 启动时恢复中断的任务状态
        self._recover_interrupted_tasks()

    def _recover_interrupted_tasks(self):
        """
        恢复因进程重启而中断的训练任务

        - 有 checkpoint 的 running/paused 任务 → 标记为 paused（可恢复）
        - 无 checkpoint 的 running 任务 → 标记为 failed
        """
        from app.database.session import SessionLocal

        db = SessionLocal()
        try:
            # 查找所有 running 或 paused 状态的任务
            interrupted_tasks = (
                db.query(TrainingTask).filter(TrainingTask.status.in_(["running", "paused"])).all()
            )

            if interrupted_tasks:
                logger.warning(f"发现 {len(interrupted_tasks)} 个中断的训练任务，正在恢复状态...")

                recovered = 0
                failed = 0
                for task in interrupted_tasks:
                    # 检查 checkpoint 是否存在
                    if task.checkpoint_path and os.path.exists(task.checkpoint_path):
                        task.status = "paused"
                        task.error_message = "服务重启导致训练中断，可从 checkpoint 恢复"
                        recovered += 1
                        logger.info(
                            f"任务 {task.id} ({task.task_uuid}) 标记为 paused（有 checkpoint）"
                        )
                    else:
                        task.status = "failed"
                        task.error_message = "服务重启导致训练中断，无 checkpoint 可恢复"
                        failed += 1
                        logger.info(
                            f"任务 {task.id} ({task.task_uuid}) 标记为 failed（无 checkpoint）"
                        )
                    task.updated_at = now_cst()

                db.commit()
                logger.info(
                    f"已恢复 {len(interrupted_tasks)} 个中断任务（{recovered} 可恢复，{failed} 失败）"
                )
            else:
                logger.info("没有发现中断的训练任务")

        except Exception as e:
            logger.error(f"恢复中断任务失败: {e}")
            db.rollback()
        finally:
            db.close()

    def create_training_task(
        self, db: Session, user_id: int, model_id: int, config: Dict[str, Any]
    ) -> TrainingTask:
        """
        创建训练任务

        Args:
            db: 数据库会话
            user_id: 用户ID
            model_id: 关联模型ID
            config: 训练配置

        Returns:
            创建的训练任务
        """
        import uuid

        task = TrainingTask(
            user_id=user_id,
            model_id=model_id,
            task_uuid=str(uuid.uuid4()),
            status="pending",
            base_architecture=config.get("base_architecture", "yolo26n"),
            epochs=config.get("epochs", 100),
            img_size=config.get("img_size", 640),
            batch_size=config.get("batch_size", 16),
            device=config.get("device", "cpu"),
            optimizer=config.get("optimizer", "SGD"),
            lr0=config.get("lr0", 0.01),
            dataset_id=config.get("dataset_id"),
            dataset_path=config.get("dataset_path"),
            data_yaml=config.get("data_yaml"),
            dataset_size=config.get("dataset_size", 0),
            set_as_default=config.get("set_as_default", False),
        )

        db.add(task)
        db.commit()
        db.refresh(task)

        logger.info(f"创建训练任务: task_id={task.id}, model_id={model_id}")
        return task

    def start_training(self, db: Session, task_id: int) -> bool:
        """
        启动训练任务

        Args:
            db: 数据库会话
            task_id: 任务ID

        Returns:
            是否成功启动
        """
        task = db.query(TrainingTask).filter(TrainingTask.id == task_id).first()
        if not task:
            logger.error(f"训练任务不存在: task_id={task_id}")
            return False

        if task.status not in ["pending", "paused", "failed"]:
            logger.error(f"任务状态不允许启动: task_id={task_id}, status={task.status}")
            return False

        # 更新任务状态
        task.status = "running"
        task.started_at = now_cst()
        task.error_message = None
        db.commit()

        # 创建停止标志并启动后台训练线程
        stop_flag = threading.Event()
        thread = threading.Thread(target=self._train_worker, args=(task_id, stop_flag), daemon=True)
        with self._lock:
            self.task_stop_flags[task_id] = stop_flag
            self.active_tasks[task_id] = thread
        thread.start()

        logger.info(f"启动训练任务: task_id={task_id}")
        return True

    def _train_worker(self, task_id: int, stop_flag: threading.Event):
        """
        训练工作线程

        Args:
            task_id: 任务ID
            stop_flag: 停止标志
        """
        from app.database.session import SessionLocal

        db = SessionLocal()
        task = None
        try:
            task = db.query(TrainingTask).filter(TrainingTask.id == task_id).first()
            if not task:
                return

            # 动态导入 ultralytics（避免启动时加载）
            try:
                from ultralytics import YOLO
            except ImportError:
                logger.error("ultralytics 未安装")
                task.status = "failed"
                task.error_message = "ultralytics 未安装"
                db.commit()
                return

            # 加载模型（优先从 checkpoint 恢复）
            base_arch = task.base_architecture
            checkpoint_path = task.checkpoint_path

            if checkpoint_path and os.path.exists(checkpoint_path):
                # 从 checkpoint 恢复训练
                model_path = checkpoint_path
                logger.info(f"从 checkpoint 恢复训练: {model_path}")
            else:
                # 从预训练模型开始
                model_path = f"{base_arch}.pt"
                logger.info(f"加载预训练模型: {model_path}")

            model = YOLO(model_path)

            # 准备训练参数
            train_args = {
                "data": task.data_yaml,
                "epochs": task.epochs,
                "imgsz": task.img_size,
                "batch": task.batch_size,
                "device": task.device,
                "optimizer": task.optimizer,
                "lr0": task.lr0,
                "project": os.path.join("runs", "train"),
                "name": f"task_{task_id}",
                "exist_ok": True,
                "verbose": True,
            }

            # 从 checkpoint 恢复时启用 resume 模式
            if checkpoint_path and os.path.exists(checkpoint_path):
                train_args["resume"] = True
                logger.info(f"启用 resume 模式，从 checkpoint 恢复: {checkpoint_path}")

            logger.info(f"开始训练: task_id={task_id}, args={train_args}")

            # 设置 YOLO 回调：更新进度并写入逐 epoch 指标
            results_csv_path = os.path.join("runs", "train", f"task_{task_id}", "results.csv")

            def _on_train_epoch_end(trainer):
                try:
                    current_ep = getattr(trainer, "epoch", 0)
                    task.current_epoch = current_ep
                    task.last_checkpoint_epoch = current_ep
                    task.progress = int((current_ep / task.epochs) * 100)

                    # 从 results.csv 读取当前 epoch 的指标并写入数据库
                    self._write_epoch_metric(db, task_id, current_ep, results_csv_path)

                    # 每 5 个 epoch 或最后一个 epoch 批量提交，减少事务开销
                    if current_ep % 5 == 0 or current_ep >= task.epochs - 1:
                        db.commit()
                except Exception:
                    db.rollback()

            model.add_callback("on_train_epoch_end", _on_train_epoch_end)

            # 执行训练
            _results = model.train(**train_args)

            # 检查是否被暂停/取消
            checkpoint_file = os.path.join("runs", "train", f"task_{task_id}", "weights", "last.pt")
            if stop_flag.is_set():
                if task.status == "paused":
                    # 暂停：保留 checkpoint 以便恢复
                    if os.path.exists(checkpoint_file):
                        task.checkpoint_path = checkpoint_file
                        task.last_checkpoint_epoch = task.current_epoch
                        logger.info(f"训练已暂停，checkpoint 已保存: {checkpoint_file}")
                    else:
                        logger.info("训练已暂停，但 checkpoint 文件不存在")
                else:
                    # 取消：清理 checkpoint 文件
                    task.status = "cancelled"
                    if os.path.exists(checkpoint_file):
                        os.remove(checkpoint_file)
                        logger.info(f"已清理取消任务的 checkpoint: {checkpoint_file}")
                    task.checkpoint_path = None
                    task.last_checkpoint_epoch = 0
                    self._invalidate_training_cache(task_id)
                    logger.info(f"训练任务已取消: task_id={task_id}")
            else:
                # 训练完成
                task.status = "completed"
                task.completed_at = now_cst()
                task.progress = 100
                task.current_epoch = task.epochs
                self._invalidate_training_cache(task_id)

                # 训练完成，清理 checkpoint
                if os.path.exists(checkpoint_file):
                    os.remove(checkpoint_file)
                task.checkpoint_path = None
                task.last_checkpoint_epoch = 0

                # 保存模型版本
                best_model_path = os.path.join(
                    "runs", "train", f"task_{task_id}", "weights", "best.pt"
                )
                if os.path.exists(best_model_path):
                    self._save_model_version(db, task, best_model_path)

                # 解析训练日志写入指标数据
                results_csv = os.path.join("runs", "train", f"task_{task_id}", "results.csv")
                self.parse_results_csv(db, task_id, results_csv)

                logger.info(f"训练任务完成: task_id={task_id}")

            db.commit()

        except Exception as e:
            logger.error(f"训练任务失败: task_id={task_id}, error={e}")
            if task is not None:
                try:
                    task.status = "failed"
                    task.error_message = str(e)
                    self._invalidate_training_cache(task_id)
                    db.commit()
                except Exception as commit_err:
                    logger.error(f"记录训练失败状态时发生数据库错误: {commit_err}")
                    try:
                        db.rollback()
                    except Exception:
                        pass
        finally:
            # 清理
            with self._lock:
                self.active_tasks.pop(task_id, None)
                self.task_stop_flags.pop(task_id, None)
            db.close()

    def _save_model_version(self, db: Session, task: TrainingTask, model_path: str):
        """
        保存模型版本

        Args:
            db: 数据库会话
            task: 训练任务
            model_path: 模型文件路径
        """
        # 获取当前模型的版本数量
        version_count = (
            db.query(ModelVersion).filter(ModelVersion.model_id == task.model_id).count()
        )

        # 计算文件大小
        file_size = os.path.getsize(model_path) if os.path.exists(model_path) else None

        version = ModelVersion(
            model_id=task.model_id,
            training_task_id=task.id,
            version=f"v{version_count + 1}.0.0",
            source="training",
            status="active",
            model_path=model_path,
            file_size=file_size,
            is_default=task.set_as_default or (version_count == 0),  # 第一个版本或用户指定
        )

        db.add(version)
        db.commit()
        logger.info(
            f"保存模型版本: model_id={task.model_id}, version={version.version}, path={model_path}"
        )

    def _write_epoch_metric(self, db: Session, task_id: int, epoch: int, results_csv_path: str):
        """
        从 results.csv 读取指定 epoch 的指标并写入 TrainingMetric

        Args:
            db: 数据库会话
            task_id: 任务ID
            epoch: 当前轮数
            results_csv_path: results.csv 文件路径
        """
        try:
            if not os.path.exists(results_csv_path):
                return

            # 已存在则跳过
            existing = (
                db.query(TrainingMetric)
                .filter(TrainingMetric.task_id == task_id, TrainingMetric.epoch == epoch)
                .first()
            )
            if existing:
                return

            # 读取 CSV 并找到对应 epoch 的行
            with open(results_csv_path, "r") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if int(row.get("epoch", -1)) == epoch:
                        metric = TrainingMetric(
                            task_id=task_id,
                            epoch=epoch,
                            box_loss=float(row.get("train/box_loss", 0)),
                            cls_loss=float(row.get("train/cls_loss", 0)),
                            dfl_loss=float(row.get("train/dfl_loss", 0)),
                            precision=float(row.get("metrics/precision(B)", 0)),
                            recall=float(row.get("metrics/recall(B)", 0)),
                            map50=float(row.get("metrics/mAP50(B)", 0)),
                            map50_95=float(row.get("metrics/mAP50-95(B)", 0)),
                            lr=float(row.get("lr/pg0", 0)),
                        )
                        db.add(metric)
                        break
        except Exception as e:
            logger.warning(f"写入 epoch {epoch} 指标失败: {e}")

    def pause_training(self, db: Session, task_id: int) -> bool:
        """
        暂停训练任务

        设置停止标志让训练线程自然停止，并保存 checkpoint 路径以便恢复。
        注意：先设置 DB 状态再设置 stop_flag，避免工作线程看到旧状态而误判为取消。

        Args:
            db: 数据库会话
            task_id: 任务ID

        Returns:
            是否成功暂停
        """
        task = db.query(TrainingTask).filter(TrainingTask.id == task_id).first()
        if not task:
            return False

        if task.status != "running":
            return False

        # 保存 checkpoint 路径（YOLO 训练时 last.pt 会自动保存在 runs/train/task_X/weights/ 下）
        checkpoint_path = os.path.join("runs", "train", f"task_{task_id}", "weights", "last.pt")
        if os.path.exists(checkpoint_path):
            task.checkpoint_path = checkpoint_path
            logger.info(f"已保存 checkpoint 路径: {checkpoint_path}")

        # 先设置 DB 状态为 paused 并提交，确保工作线程在检查 stop_flag 时
        # 已经能看到正确的状态，避免“先设 flag 再改 status”导致的竞态条件
        task.status = "paused"
        db.commit()

        # 设置停止标志（放在状态提交之后）
        with self._lock:
            stop_flag = self.task_stop_flags.get(task_id)
        if stop_flag:
            stop_flag.set()

        logger.info(f"暂停训练任务: task_id={task_id}")
        return True

    def cancel_training(self, db: Session, task_id: int) -> bool:
        """
        取消训练任务

        Args:
            db: 数据库会话
            task_id: 任务ID

        Returns:
            是否成功取消
        """
        task = db.query(TrainingTask).filter(TrainingTask.id == task_id).first()
        if not task:
            return False

        if task.status not in ["running", "paused", "pending"]:
            return False

        # 设置停止标志
        with self._lock:
            stop_flag = self.task_stop_flags.get(task_id)
        if stop_flag:
            stop_flag.set()

        task.status = "cancelled"
        self._invalidate_training_cache(task_id)
        db.commit()

        # 注意：checkpoint 文件的实际清理由 _train_worker 线程完成
        # 这里只清理已暂停任务的历史 checkpoint（线程已停止的情况）
        if task.checkpoint_path and os.path.exists(task.checkpoint_path):
            try:
                cp_path = task.checkpoint_path
                os.remove(cp_path)
                task.checkpoint_path = None
                db.commit()
                logger.info(f"已清理暂停任务的 checkpoint: {cp_path}")
            except Exception as e:
                logger.warning(f"清理 checkpoint 失败: {e}")

        logger.info(f"取消训练任务: task_id={task_id}")
        return True

    def delete_training_task(self, db: Session, task_id: int) -> bool:
        """
        删除训练任务

        仅允许删除非运行中的任务（pending/paused/completed/failed/cancelled）
        同时清理关联的 checkpoint 文件和训练指标

        Args:
            db: 数据库会话
            task_id: 任务ID

        Returns:
            是否成功删除
        """
        task = db.query(TrainingTask).filter(TrainingTask.id == task_id).first()
        if not task:
            return False

        # 运行中的任务不允许删除，需先取消
        if task.status == "running":
            logger.warning(f"无法删除运行中的任务: task_id={task_id}")
            return False

        # 停止线程（针对 paused 状态可能残留的线程）
        with self._lock:
            stop_flag = self.task_stop_flags.get(task_id)
        if stop_flag:
            stop_flag.set()

        # 清理 checkpoint 文件
        if task.checkpoint_path and os.path.exists(task.checkpoint_path):
            try:
                os.remove(task.checkpoint_path)
                logger.info(f"已清理 checkpoint: {task.checkpoint_path}")
            except Exception as e:
                logger.warning(f"清理 checkpoint 失败: {e}")

        # 清理关联的训练指标
        db.query(TrainingMetric).filter(TrainingMetric.task_id == task_id).delete()

        # 清理缓存
        self._invalidate_training_cache(task_id)

        # 删除任务记录
        db.delete(task)
        db.commit()

        logger.info(f"删除训练任务: task_id={task_id}")
        return True

    def _invalidate_training_cache(self, task_id: int) -> None:
        """清除训练状态 Redis 缓存"""
        redis_client.cache_delete("training_status", str(task_id))

    def get_training_status(self, db: Session, task_id: int) -> Optional[Dict[str, Any]]:
        """
        获取训练状态（支持 Redis 缓存）

        Args:
            db: 数据库会话
            task_id: 任务ID

        Returns:
            训练状态字典
        """
        # 尝试从 Redis 缓存获取（5 秒 TTL）
        cached = redis_client.cache_get("training_status", str(task_id))
        if cached:
            return cached

        task = db.query(TrainingTask).filter(TrainingTask.id == task_id).first()
        if not task:
            return None

        result = {
            "task_id": task.id,
            "status": task.status,
            "current_epoch": task.current_epoch,
            "total_epochs": task.epochs,
            "progress": task.progress,
            "started_at": task.started_at.isoformat() if task.started_at else None,
            "completed_at": task.completed_at.isoformat() if task.completed_at else None,
            "error_message": task.error_message,
        }

        # 写入缓存，训练中使用 5 秒 TTL，完成状态使用 60 秒 TTL
        ttl = 5 if task.status in ("running", "paused") else 60
        redis_client.cache_set("training_status", str(task_id), result, ex=ttl)

        return result

    def get_training_metrics(self, db: Session, task_id: int) -> List[Dict[str, Any]]:
        """
        获取训练指标

        Args:
            db: 数据库会话
            task_id: 任务ID

        Returns:
            训练指标列表
        """
        metrics = (
            db.query(TrainingMetric)
            .filter(TrainingMetric.task_id == task_id)
            .order_by(TrainingMetric.epoch)
            .all()
        )

        return [
            {
                "epoch": m.epoch,
                "box_loss": m.box_loss,
                "cls_loss": m.cls_loss,
                "dfl_loss": m.dfl_loss,
                "precision": m.precision,
                "recall": m.recall,
                "map50": m.map50,
                "map50_95": m.map50_95,
                "lr": m.lr,
            }
            for m in metrics
        ]

    def parse_results_csv(self, db: Session, task_id: int, results_csv: str) -> bool:
        """
        解析训练日志 results.csv

        Args:
            db: 数据库会话
            task_id: 任务ID
            results_csv: results.csv 文件路径

        Returns:
            是否成功解析
        """
        try:
            if not os.path.exists(results_csv):
                logger.warning(f"results.csv 不存在: {results_csv}")
                return False

            with open(results_csv, "r") as f:
                reader = csv.DictReader(f)

                for row in reader:
                    epoch = int(row.get("epoch", 0))

                    # 检查是否已存在
                    existing = (
                        db.query(TrainingMetric)
                        .filter(TrainingMetric.task_id == task_id, TrainingMetric.epoch == epoch)
                        .first()
                    )

                    if existing:
                        continue

                    # 创建指标记录
                    metric = TrainingMetric(
                        task_id=task_id,
                        epoch=epoch,
                        box_loss=float(row.get("train/box_loss", 0)),
                        cls_loss=float(row.get("train/cls_loss", 0)),
                        dfl_loss=float(row.get("train/dfl_loss", 0)),
                        precision=float(row.get("metrics/precision(B)", 0)),
                        recall=float(row.get("metrics/recall(B)", 0)),
                        map50=float(row.get("metrics/mAP50(B)", 0)),
                        map50_95=float(row.get("metrics/mAP50-95(B)", 0)),
                        lr=float(row.get("lr/pg0", 0)),
                    )
                    db.add(metric)

                db.commit()
                logger.info(f"解析 results.csv 完成: task_id={task_id}")
                return True

        except Exception as e:
            logger.error(f"解析 results.csv 失败: {e}")
            return False

    def validate_model(
        self,
        db: Session,
        task_id: int,
        data_yaml: Optional[str] = None,
        img_size: int = 640,
        batch_size: int = 16,
    ) -> Optional[Dict[str, Any]]:
        """
        模型评估

        Args:
            db: 数据库会话
            task_id: 训练任务ID
            data_yaml: 数据集配置文件路径（可选，默认使用训练时的配置）
            img_size: 图像尺寸
            batch_size: 批次大小

        Returns:
            评估结果字典
        """
        # 获取任务信息
        task = db.query(TrainingTask).filter(TrainingTask.id == task_id).first()
        if not task:
            logger.error(f"训练任务不存在: task_id={task_id}")
            return None

        # 检查任务状态
        if task.status not in ["completed", "failed"]:
            logger.error(f"任务状态不允许评估: task_id={task_id}, status={task.status}")
            return None

        # 获取模型路径
        model_version = (
            db.query(ModelVersion)
            .filter(ModelVersion.training_task_id == task_id, ModelVersion.status == "active")
            .first()
        )

        if not model_version:
            logger.error(f"未找到训练产出的模型: task_id={task_id}")
            return None

        model_path = model_version.model_path
        if not os.path.exists(model_path):
            logger.error(f"模型文件不存在: {model_path}")
            return None

        # 使用训练时的数据集配置或指定的配置
        eval_data_yaml = data_yaml or task.data_yaml
        if not eval_data_yaml:
            logger.error(f"未指定数据集配置: task_id={task_id}")
            return None

        try:
            from ultralytics import YOLO

            logger.info(f"开始模型评估: task_id={task_id}, model={model_path}")

            # 加载模型
            model = YOLO(model_path)

            # 执行评估
            results = model.val(data=eval_data_yaml, imgsz=img_size, batch=batch_size, verbose=True)

            # 提取评估指标
            eval_result = {
                "task_id": task_id,
                "model_path": model_path,
                "metrics": {
                    "mAP50": float(results.box.map50),
                    "mAP50-95": float(results.box.map),
                    "precision": float(results.box.mp),
                    "recall": float(results.box.mr),
                    "f1": float(results.box.f1),
                },
                "per_class_ap": {},
                "confusion_matrix": results.confusion_matrix.matrix.tolist()
                if results.confusion_matrix
                else None,
                "evaluated_at": now_cst().isoformat(),
            }

            # 提取各类别 AP
            if hasattr(results.box, "ap_class_index") and hasattr(results, "names"):
                for idx, ap in enumerate(results.box.ap):
                    class_name = results.names.get(idx, f"class_{idx}")
                    eval_result["per_class_ap"][class_name] = float(ap)

            # 更新模型版本的评估指标
            model_version.map50 = eval_result["metrics"]["mAP50"]
            model_version.map50_95 = eval_result["metrics"]["mAP50-95"]
            model_version.precision = eval_result["metrics"]["precision"]
            model_version.recall = eval_result["metrics"]["recall"]
            model_version.per_class_ap = eval_result["per_class_ap"]
            db.commit()

            logger.info(
                f"模型评估完成: task_id={task_id}, mAP50={eval_result['metrics']['mAP50']:.4f}"
            )
            return eval_result

        except Exception as e:
            logger.error(f"模型评估失败: task_id={task_id}, error={e}")
            return None

    def get_task_list(
        self,
        db: Session,
        user_id: Optional[int] = None,
        model_id: Optional[int] = None,
        status: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Dict[str, Any]:
        """
        获取训练任务列表

        Args:
            db: 数据库会话
            user_id: 用户ID（可选）
            model_id: 模型ID（可选）
            status: 状态（可选）
            page: 页码
            page_size: 每页数量

        Returns:
            分页结果
        """
        query = db.query(TrainingTask)

        if user_id:
            query = query.filter(TrainingTask.user_id == user_id)
        if model_id:
            query = query.filter(TrainingTask.model_id == model_id)
        if status:
            query = query.filter(TrainingTask.status == status)

        total = query.count()
        tasks = (
            query.order_by(TrainingTask.created_at.desc())
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
                    "task_uuid": t.task_uuid,
                    "status": t.status,
                    "model_id": t.model_id,
                    "base_architecture": t.base_architecture,
                    "epochs": t.epochs,
                    "current_epoch": t.current_epoch,
                    "progress": t.progress,
                    "batch_size": t.batch_size,
                    "lr0": t.lr0,
                    "device": t.device,
                    "last_checkpoint_epoch": t.last_checkpoint_epoch,
                    "created_at": t.created_at.isoformat() if t.created_at else None,
                }
                for t in tasks
            ],
        }


# 全局训练服务实例
training_service = TrainingService()
