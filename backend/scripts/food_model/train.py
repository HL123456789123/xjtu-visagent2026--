#!/usr/bin/env python3
"""在单张 RTX GPU 上训练食品 YOLO11 检测模型。

此脚本不依赖 VisAgent 的通用训练任务服务，以避免其当前 YOLO26 架构和食品
YOLO11 实验混用。输出目录必须位于 ``/root/autodl-tmp/visagent/reports``。
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import torch
import yaml
from ultralytics import YOLO
from ultralytics.utils.autobatch import check_train_batch_size


DEFAULT_MODEL_PATHS = {
    "yolo11n": Path("/root/yolov11/model/yolo11n.pt"),
    "yolo11s": Path("/root/yolov11/model/yolo11s.pt"),
    "yolo11m": Path("/root/yolov11/model/yolo11m.pt"),
}


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_training_image_count(data_yaml: Path) -> int:
    payload = yaml.safe_load(data_yaml.read_text(encoding="utf-8"))
    root = Path(payload.get("path", data_yaml.parent))
    train = Path(payload["train"])
    train_path = train if train.is_absolute() else root / train
    if not train_path.is_dir():
        raise FileNotFoundError(f"训练图片目录不存在: {train_path}")
    return sum(1 for path in train_path.iterdir() if path.is_file())


def nearest_batch_multiple(value: int, multiple: int = 8) -> int:
    return max(multiple, value // multiple * multiple)


def determine_batch_size(model: YOLO, *, image_count: int, image_size: int, memory_fraction: float) -> dict[str, int]:
    """探测显存上限，同时保证一个 epoch 至少约 32 次参数更新。"""
    if not torch.cuda.is_available():
        raise RuntimeError("训练要求 CUDA GPU，但当前 PyTorch 没有检测到可用 CUDA")
    # YOLO 刚从权重构造时仍在 CPU；若不先迁移，Ultralytics 会静默退回默认 batch=16，
    # 既没有真正探测 85% 显存，也浪费 4090 的吞吐。
    model.model.to("cuda:0")
    try:
        auto_batch = check_train_batch_size(
            model.model,
            imgsz=image_size,
            amp=True,
            batch=memory_fraction,
            dataset_size=image_count,
        )
    finally:
        # `YOLO.train()` 会在 CPU 上新建 Trainer 模型再加载预训练权重；保留 CUDA
        # 权重会导致其分类头重映射出现 CPU/CUDA 张量混用。
        model.model.to("cpu")
        torch.cuda.empty_cache()
    max_batch_for_steps = nearest_batch_multiple(max(8, image_count // 32))
    selected = nearest_batch_multiple(min(auto_batch, max_batch_for_steps))
    return {
        "auto_batch_85pct_vram": int(auto_batch),
        "max_batch_for_32_steps": int(max_batch_for_steps),
        "selected_batch": int(selected),
    }


def resolve_weights(architecture: str, explicit_weights: Path | None) -> Path:
    if explicit_weights:
        path = explicit_weights.resolve()
        if not path.is_file():
            raise FileNotFoundError(f"指定的预训练权重不存在: {path}")
        return path
    path = DEFAULT_MODEL_PATHS[architecture]
    if not path.is_file():
        raise FileNotFoundError(
            f"未找到 {architecture} 预训练权重: {path}。请先下载到该位置，或传入 --weights。"
        )
    return path


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, required=True, help="prepare_dataset.py 输出的 data.yaml")
    parser.add_argument("--architecture", choices=tuple(DEFAULT_MODEL_PATHS), required=True)
    parser.add_argument("--weights", type=Path, help="可选的 YOLO11 预训练权重路径")
    parser.add_argument("--epochs", type=int, required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--name", required=True, help="本次实验的稳定目录名")
    parser.add_argument(
        "--run-root",
        type=Path,
        default=Path("/root/autodl-tmp/visagent/reports/food/runs"),
    )
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--workers", type=int, default=16)
    parser.add_argument("--patience", type=int, default=20)
    parser.add_argument("--memory-fraction", type=float, default=0.85)
    parser.add_argument("--smoke", action="store_true", help="标记本次为 1 epoch 冒烟训练")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.epochs < 1:
        raise ValueError("epochs 必须大于等于 1")
    if not 0 < args.memory_fraction < 1:
        raise ValueError("memory-fraction 必须位于 0 和 1 之间")
    if not torch.cuda.is_available():
        raise RuntimeError("未检测到 CUDA；请使用 /root/autodl-tmp/visagent/.venv-yolo/bin/python 运行")

    data_yaml = args.data.resolve()
    if not data_yaml.is_file():
        raise FileNotFoundError(f"data.yaml 不存在: {data_yaml}")
    run_root = args.run_root.resolve()
    run_directory = run_root / args.name
    if run_directory.exists():
        raise FileExistsError(f"实验目录已存在，拒绝覆盖: {run_directory}")
    weights = resolve_weights(args.architecture, args.weights)
    image_count = load_training_image_count(data_yaml)

    torch.cuda.set_device(0)
    model = YOLO(str(weights))
    batch_info = determine_batch_size(
        model,
        image_count=image_count,
        image_size=args.imgsz,
        memory_fraction=args.memory_fraction,
    )
    config = {
        "started_at": utc_timestamp(),
        "architecture": args.architecture,
        "weights": str(weights),
        "data": str(data_yaml),
        "epochs": args.epochs,
        "seed": args.seed,
        "image_count": image_count,
        "imgsz": args.imgsz,
        "workers": args.workers,
        "patience": args.patience,
        "device": 0,
        "cuda_device_name": torch.cuda.get_device_name(0),
        "cuda_total_memory_bytes": torch.cuda.get_device_properties(0).total_memory,
        "batch": batch_info,
        "smoke": args.smoke,
    }
    write_json(run_directory / "experiment_config.json", config)

    model.train(
        data=str(data_yaml),
        epochs=args.epochs,
        imgsz=args.imgsz,
        batch=batch_info["selected_batch"],
        device=0,
        workers=args.workers,
        cache="ram",
        amp=True,
        optimizer="auto",
        patience=args.patience,
        seed=args.seed,
        deterministic=True,
        pretrained=True,
        close_mosaic=10,
        project=str(run_root),
        name=args.name,
        # experiment_config.json 已在新目录中写入；允许 YOLO 使用该同名空实验目录。
        exist_ok=True,
        save=True,
        save_period=-1,
        val=True,
        plots=True,
        verbose=True,
    )
    config["finished_at"] = utc_timestamp()
    config["best_weights"] = str(run_directory / "weights" / "best.pt")
    config["last_weights"] = str(run_directory / "weights" / "last.pt")
    write_json(run_directory / "experiment_config.json", config)
    print(json.dumps(config, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    # 训练过程使用单卡；不要在同一张 RTX 4090 上并行启动多个本脚本实例。
    os.environ.setdefault("CUDA_VISIBLE_DEVICES", "0")
    main()
