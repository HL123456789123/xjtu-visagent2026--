#!/usr/bin/env python3
"""按三种子验证均值和 P95 GPU 延迟，在 YOLO11s/YOLO11m 间确定冠军。"""

from __future__ import annotations

import argparse
import csv
import json
import math
import time
from pathlib import Path

import torch
import yaml
from ultralytics import YOLO


SEEDS = (42, 2026, 3407)


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def best_validation_map(run_directory: Path) -> float:
    results = run_directory / "results.csv"
    if not results.is_file():
        raise FileNotFoundError(f"缺少实验结果: {results}")
    with results.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise ValueError(f"实验没有结果行: {results}")
    field = next((name for name in rows[0] if "metrics/mAP50-95" in name), None)
    if field is None:
        raise ValueError(f"{results} 缺少 mAP50-95 字段")
    values = [float(row[field]) for row in rows if row.get(field)]
    if not values:
        raise ValueError(f"{results} 的 mAP50-95 为空")
    return max(values)


def validation_images(data_yaml: Path) -> list[Path]:
    data = yaml.safe_load(data_yaml.read_text(encoding="utf-8")) or {}
    root = Path(data.get("path", data_yaml.parent))
    value = Path(data["val"])
    directory = value if value.is_absolute() else root / value
    return sorted(path for path in directory.iterdir() if path.is_file())


def latency_p95(weights: Path, images: list[Path], *, samples: int, imgsz: int) -> dict[str, float | int]:
    if not images:
        raise ValueError("验证图片为空，无法测量延迟")
    model = YOLO(str(weights))
    selected = images[: min(samples, len(images))]
    model.predict(source=str(selected[0]), imgsz=imgsz, device=0, half=True, verbose=False)
    torch.cuda.synchronize(0)
    timings: list[float] = []
    for image in selected:
        torch.cuda.synchronize(0)
        started = time.perf_counter()
        model.predict(source=str(image), imgsz=imgsz, device=0, half=True, verbose=False)
        torch.cuda.synchronize(0)
        timings.append((time.perf_counter() - started) * 1000)
    ordered = sorted(timings)
    p95_index = min(len(ordered) - 1, math.ceil(len(ordered) * 0.95) - 1)
    return {"samples": len(timings), "p50_ms": ordered[len(ordered) // 2], "p95_ms": ordered[p95_index]}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs-root", type=Path, default=Path("/root/autodl-tmp/visagent/reports/food/runs"))
    parser.add_argument(
        "--run-prefix",
        default="food12",
        help="实验目录共同前缀；例如 food12v2_yolo11s_seed42",
    )
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--latency-samples", type=int, default=100)
    parser.add_argument("--imgsz", type=int, default=640)
    args = parser.parse_args()
    if not torch.cuda.is_available():
        raise RuntimeError("冠军选择的延迟测量要求 CUDA")

    records: dict[str, list[dict]] = {}
    for architecture in ("yolo11s", "yolo11m"):
        current: list[dict] = []
        for seed in SEEDS:
            run_directory = args.runs_root / f"{args.run_prefix}_{architecture}_seed{seed}"
            weights = run_directory / "weights" / "best.pt"
            if not weights.is_file():
                raise FileNotFoundError(f"缺少权重: {weights}")
            current.append(
                {
                    "seed": seed,
                    "run_directory": str(run_directory),
                    "weights": str(weights),
                    "best_val_map50_95": best_validation_map(run_directory),
                }
            )
        records[architecture] = current
    means = {architecture: sum(item["best_val_map50_95"] for item in values) / len(values) for architecture, values in records.items()}
    images = validation_images(args.data.resolve())
    architecture_latency = {}
    for architecture, values in records.items():
        best_run = sorted(values, key=lambda item: (-item["best_val_map50_95"], item["seed"]))[0]
        architecture_latency[architecture] = latency_p95(
            Path(best_run["weights"]), images, samples=args.latency_samples, imgsz=args.imgsz
        )
    m_beats_s = means["yolo11m"] - means["yolo11s"] >= 0.015
    m_meets_latency = float(architecture_latency["yolo11m"]["p95_ms"]) <= 50.0
    architecture = "yolo11m" if m_beats_s and m_meets_latency else "yolo11s"
    chosen_run = sorted(records[architecture], key=lambda item: (-item["best_val_map50_95"], item["seed"]))[0]
    result = {
        "schema_version": 1,
        "run_prefix": args.run_prefix,
        "selection_rule": "choose yolo11m only if mean mAP50-95 gain >= 0.015 and m P95 <= 50ms; otherwise yolo11s",
        "validation_mean_map50_95": means,
        "architecture_latency": architecture_latency,
        "m_gain_over_s": means["yolo11m"] - means["yolo11s"],
        "m_beats_s_by_0_015": m_beats_s,
        "m_p95_within_50ms": m_meets_latency,
        "chosen_architecture": architecture,
        "chosen_run": chosen_run,
        "all_runs": records,
    }
    write_json(args.output.resolve(), result)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
