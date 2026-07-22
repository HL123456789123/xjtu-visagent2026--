#!/usr/bin/env python3
"""评估食品 YOLO11 模型、输出逐类指标并生成严格 12 类选择文件。"""

from __future__ import annotations

import argparse
import csv
import json
import math
import random
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import torch
import yaml
from PIL import Image
from ultralytics import YOLO

from catalog import SOURCE_NAMES, output_definition


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def load_data(data_yaml: Path) -> tuple[dict[str, Any], list[str], Path]:
    data = yaml.safe_load(data_yaml.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"无效 data.yaml: {data_yaml}")
    raw_names = data["names"]
    if isinstance(raw_names, dict):
        names = [str(raw_names[index]) for index in sorted(raw_names, key=lambda value: int(value))]
    else:
        names = [str(item) for item in raw_names]
    root = Path(data.get("path", data_yaml.parent))
    return data, names, root


def split_images(data: dict[str, Any], root: Path, split: str) -> list[Path]:
    key = "val" if split == "val" else split
    value = Path(data[key])
    directory = value if value.is_absolute() else root / value
    if not directory.is_dir():
        raise FileNotFoundError(f"{split} 图片目录不存在: {directory}")
    return sorted(path for path in directory.iterdir() if path.is_file())


def sequence(values: Any) -> list[float]:
    if values is None:
        return []
    if hasattr(values, "tolist"):
        values = values.tolist()
    return [float(value) for value in values]


def operating_point_metrics(results: Any, names: list[str]) -> tuple[dict[int, dict[str, float]], dict[str, float]]:
    """从验证器的混淆矩阵提取给定置信度阈值下的 P/R。

    Ultralytics ``box.p`` / ``box.r`` 是 F1 最优阈值处的点，不能替代选择公式要求的
    Recall@0.25。验证器已按 ``model.val(conf=0.25)`` 构建 confusion matrix，故这里直接
    从该矩阵计算同一工作点下的精确率与召回率。
    """
    confusion = getattr(results, "confusion_matrix", None)
    matrix = getattr(confusion, "matrix", None)
    if matrix is None or len(matrix) < len(names):
        return {}, {"precision": 0.0, "recall": 0.0}
    values = matrix.tolist() if hasattr(matrix, "tolist") else matrix
    per_class: dict[int, dict[str, float]] = {}
    total_tp = total_fp = total_fn = 0.0
    for class_id in range(len(names)):
        tp = float(values[class_id][class_id])
        fp = float(sum(values[class_id]) - tp)
        fn = float(sum(row[class_id] for row in values) - tp)
        per_class[class_id] = {
            "precision": tp / (tp + fp) if tp + fp else 0.0,
            "recall": tp / (tp + fn) if tp + fn else 0.0,
        }
        total_tp += tp
        total_fp += fp
        total_fn += fn
    return per_class, {
        "precision": total_tp / (total_tp + total_fp) if total_tp + total_fp else 0.0,
        "recall": total_tp / (total_tp + total_fn) if total_tp + total_fn else 0.0,
    }


def extract_metrics(results: Any, names: list[str]) -> dict[str, Any]:
    box = results.box
    class_indices = [int(value) for value in sequence(getattr(box, "ap_class_index", []))]
    ap = sequence(getattr(box, "ap", []))
    ap50 = sequence(getattr(box, "ap50", []))
    precision = sequence(getattr(box, "p", []))
    recall = sequence(getattr(box, "r", []))
    operating_per_class, operating_overall = operating_point_metrics(results, names)
    if not class_indices:
        class_indices = list(range(len(ap)))
    per_class: list[dict[str, Any]] = []
    for position, class_id in enumerate(class_indices):
        if not 0 <= class_id < len(names):
            continue
        per_class.append(
            {
                "class_id": class_id,
                "source_name": names[class_id],
                "precision": operating_per_class.get(class_id, {}).get(
                    "precision", precision[position] if position < len(precision) else 0.0
                ),
                "recall": operating_per_class.get(class_id, {}).get(
                    "recall", recall[position] if position < len(recall) else 0.0
                ),
                "ap50": ap50[position] if position < len(ap50) else 0.0,
                "ap50_95": ap[position] if position < len(ap) else 0.0,
            }
        )
    result_dict = getattr(results, "results_dict", {})
    return {
        "overall": {
            "precision": operating_overall["precision"],
            "recall": operating_overall["recall"],
            "map50": float(getattr(box, "map50", 0.0)),
            "map50_95": float(getattr(box, "map", 0.0)),
            "speed_ms": {key: float(value) for key, value in result_dict.items() if "speed" in key.lower()},
        },
        "per_class": sorted(per_class, key=lambda item: item["class_id"]),
    }


def latency_measurement(model: YOLO, images: list[Path], *, image_size: int, conf: float, limit: int) -> dict[str, Any]:
    """只测 GPU 推理，不把模型加载、文件发现和报告写入计入延迟。"""
    selected = images[: min(limit, len(images))]
    if not selected:
        return {"samples": 0, "p50_ms": None, "p95_ms": None, "mean_ms": None}
    model.predict(source=str(selected[0]), imgsz=image_size, conf=conf, device=0, half=True, verbose=False)
    torch.cuda.synchronize(0)
    durations: list[float] = []
    for image in selected:
        torch.cuda.synchronize(0)
        started = time.perf_counter()
        model.predict(source=str(image), imgsz=image_size, conf=conf, device=0, half=True, verbose=False)
        torch.cuda.synchronize(0)
        durations.append((time.perf_counter() - started) * 1000)
    ordered = sorted(durations)
    p95_index = min(len(ordered) - 1, math.ceil(len(ordered) * 0.95) - 1)
    return {
        "samples": len(durations),
        "p50_ms": ordered[len(ordered) // 2],
        "p95_ms": ordered[p95_index],
        "mean_ms": sum(durations) / len(durations),
    }


def fixed_image_report(
    model: YOLO,
    images: list[Path],
    report_root: Path,
    *,
    image_size: int,
    conf: float,
) -> list[dict[str, Any]]:
    """保留可复跑的单图、多目标图和空白图推理证据。"""
    if not images:
        return []
    fixed_root = report_root / "fixed_inputs"
    fixed_root.mkdir(parents=True, exist_ok=True)
    blank_path = fixed_root / "blank.png"
    Image.new("RGB", (image_size, image_size), color=(0, 0, 0)).save(blank_path)
    inputs = [("single_or_regular", images[0]), ("multi_ingredient", images[min(1, len(images) - 1)]), ("blank", blank_path)]
    report: list[dict[str, Any]] = []
    for label, image in inputs:
        result = model.predict(source=str(image), imgsz=image_size, conf=conf, device=0, half=True, verbose=False)[0]
        detections = []
        boxes = getattr(result, "boxes", None)
        if boxes is not None:
            for box in boxes:
                x1, y1, x2, y2 = (float(value) for value in box.xyxy[0].tolist())
                class_id = int(box.cls[0].item())
                detections.append(
                    {
                        "class_id": class_id,
                        "class_name": str(result.names[class_id]),
                        "confidence": float(box.conf[0].item()),
                        "bbox": {"x1": x1, "y1": y1, "x2": x2, "y2": y2},
                    }
                )
        report.append({"case": label, "image_path": str(image), "detections": detections})
    return report


def load_source_coverage(distribution_csv: Path) -> dict[str, dict[str, int]]:
    coverage: dict[str, dict[str, int]] = defaultdict(dict)
    with distribution_csv.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            coverage[row["source_name"]][row["split"]] = int(row["unique_source_groups"])
    return coverage


def load_audit(audit_file: Path) -> dict[str, dict[str, Any]]:
    rows: dict[str, list[dict[str, str]]] = defaultdict(list)
    with audit_file.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            rows[row["source_name"]].append(row)
    summary: dict[str, dict[str, Any]] = {}
    for source_name, class_rows in rows.items():
        statuses = [row["review_status"].strip().lower() for row in class_rows]
        failures = sum(status == "fail" for status in statuses)
        pending = sum(status not in {"pass", "fail"} for status in statuses)
        summary[source_name] = {
            "samples": len(class_rows),
            "failures": failures,
            "pending": pending,
            "error_rate": failures / len(class_rows) if class_rows else 1.0,
            "strict_pass": len(class_rows) == 30 and pending == 0 and failures <= 1,
        }
    return summary


def create_selection(
    *,
    metrics: dict[str, Any],
    distribution_csv: Path,
    audit_file: Path,
) -> dict[str, Any]:
    """将验证集指标、独立源图数和人工审计结合成完全确定的 12 类选择。"""
    coverage = load_source_coverage(distribution_csv)
    audit = load_audit(audit_file)
    metric_by_name = {item["source_name"]: item for item in metrics["per_class"]}
    candidates: list[dict[str, Any]] = []
    maximum_sources = max((values.get("train", 0) for values in coverage.values()), default=1)
    for source_id, source_name in enumerate(SOURCE_NAMES):
        metric = metric_by_name.get(source_name, {})
        source_counts = coverage.get(source_name, {})
        audit_info = audit.get(source_name, {"samples": 0, "failures": 0, "pending": 30, "error_rate": 1.0, "strict_pass": False})
        eligible = (
            source_counts.get("train", 0) >= 60
            and source_counts.get("val", 0) >= 10
            and audit_info["strict_pass"]
        )
        coverage_score = math.log1p(source_counts.get("train", 0)) / math.log1p(maximum_sources)
        score = (
            0.50 * float(metric.get("ap50_95", 0.0))
            + 0.25 * float(metric.get("recall", 0.0))
            + 0.15 * coverage_score
            + 0.10 * float(metric.get("ap50", 0.0))
        )
        definition = output_definition(source_name)
        candidates.append(
            {
                "source_id": source_id,
                "source_name": source_name,
                "class_name": definition.class_name,
                "display_name": definition.display_name,
                "eligible": eligible,
                "selection_score": score,
                "source_coverage": source_counts,
                "audit": audit_info,
                "metrics": metric,
            }
        )
    eligible = [candidate for candidate in candidates if candidate["eligible"]]
    eligible.sort(
        key=lambda item: (
            -item["selection_score"],
            -float(item["metrics"].get("ap50", 0.0)),
            -item["source_coverage"].get("train", 0),
            item["source_id"],
        )
    )
    selected = eligible[:12]
    return {
        "schema_version": 1,
        "selection_formula": "0.50*AP50-95 + 0.25*Recall@0.25 + 0.15*source_coverage + 0.10*AP50",
        "strict_audit_passed": len(selected) == 12,
        "selected_classes": selected,
        "all_candidates": candidates,
        "rejection_reason": "可通过严格人工审计且覆盖度足够的类别少于 12 个" if len(selected) < 12 else None,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--weights", type=Path, required=True)
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--split", choices=("val", "test"), default="val")
    parser.add_argument("--report-root", type=Path, required=True)
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--batch", type=int, default=64)
    parser.add_argument("--conf", type=float, default=0.25)
    parser.add_argument("--latency-samples", type=int, default=100)
    parser.add_argument("--select-classes", action="store_true", help="仅允许对 30 类验证集生成选择文件")
    parser.add_argument("--distribution-csv", type=Path)
    parser.add_argument("--audit-file", type=Path)
    parser.add_argument("--selection-output", type=Path)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if not torch.cuda.is_available():
        raise RuntimeError("评估要求 CUDA GPU")
    if not 0 <= args.conf <= 1:
        raise ValueError("conf 必须位于 0 和 1 之间")
    weights = args.weights.resolve()
    data_yaml = args.data.resolve()
    report_root = args.report_root.resolve()
    if not weights.is_file() or not data_yaml.is_file():
        raise FileNotFoundError("weights 或 data.yaml 不存在")
    data, names, root = load_data(data_yaml)
    images = split_images(data, root, args.split)
    model = YOLO(str(weights))
    validation = model.val(
        data=str(data_yaml),
        split=args.split,
        imgsz=args.imgsz,
        batch=args.batch,
        device=0,
        half=True,
        # AP50/AP50-95 必须由完整置信度曲线计算。Ultralytics 在 val 的默认 0.001
        # 会保留该曲线，同时其 ConfusionMatrix 会按框架规则使用 0.25 工作点，
        # 供上面的 Recall@0.25 提取函数读取。
        conf=0.001,
        plots=True,
        project=str(report_root),
        name=f"ultralytics_{args.split}",
        exist_ok=True,
        verbose=True,
    )
    metrics = extract_metrics(validation, names)
    metrics["weights"] = str(weights)
    metrics["data"] = str(data_yaml)
    metrics["split"] = args.split
    metrics["conf_threshold"] = args.conf
    metrics["latency"] = latency_measurement(
        model, images, image_size=args.imgsz, conf=args.conf, limit=args.latency_samples
    )
    metrics["fixed_images"] = fixed_image_report(
        model, images, report_root, image_size=args.imgsz, conf=args.conf
    )
    output = report_root / f"metrics_{args.split}.json"
    write_json(output, metrics)

    if args.select_classes:
        if args.split != "val" or names != SOURCE_NAMES:
            raise ValueError("类别选择仅允许对无泄漏 30 类验证集执行")
        if args.conf != 0.25:
            raise ValueError("类别选择的 Recall 必须固定使用 conf=0.25")
        if not args.distribution_csv or not args.audit_file or not args.selection_output:
            raise ValueError("类别选择必须提供 --distribution-csv、--audit-file 和 --selection-output")
        selection = create_selection(
            metrics=metrics,
            distribution_csv=args.distribution_csv.resolve(),
            audit_file=args.audit_file.resolve(),
        )
        write_json(args.selection_output.resolve(), selection)
        print(json.dumps(selection, ensure_ascii=False, indent=2))
    print(json.dumps({"metrics_output": str(output), "overall": metrics["overall"], "latency": metrics["latency"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
