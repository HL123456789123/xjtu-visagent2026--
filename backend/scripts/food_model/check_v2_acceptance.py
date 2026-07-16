#!/usr/bin/env python3
"""根据食品识别 V2 的逐类门槛生成可审计的发布判定。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


V2_MIN_OVERALL_MAP50_95 = 0.65
V2_MIN_PER_CLASS_RECALL = 0.70
V2_MIN_PER_CLASS_AP50_95 = 0.50
V2_MAX_P95_MS = 15.0
V1_MIN_OVERALL_MAP50_95 = 0.6285875240849454
V1_WEAK_CLASS_MIN_AP50_95 = {"beef": 0.046608895137120944, "carrot": 0.311999532359833}


def load_metrics(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or not isinstance(payload.get("overall"), dict):
        raise ValueError(f"无效评估报告: {path}")
    return payload


def validate_v2(metrics: dict[str, Any]) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    overall = metrics["overall"]
    if float(overall.get("map50_95", 0.0)) < V2_MIN_OVERALL_MAP50_95:
        failures.append({"scope": "overall", "metric": "map50_95", "minimum": V2_MIN_OVERALL_MAP50_95, "actual": overall.get("map50_95")})
    p95 = metrics.get("latency", {}).get("p95_ms")
    if p95 is None or float(p95) > V2_MAX_P95_MS:
        failures.append({"scope": "latency", "metric": "p95_ms", "maximum": V2_MAX_P95_MS, "actual": p95})
    for item in metrics.get("per_class", []):
        name = str(item.get("source_name", ""))
        recall = float(item.get("recall", 0.0))
        ap = float(item.get("ap50_95", 0.0))
        if recall < V2_MIN_PER_CLASS_RECALL:
            failures.append({"scope": name, "metric": "recall_at_0.25", "minimum": V2_MIN_PER_CLASS_RECALL, "actual": recall})
        if ap < V2_MIN_PER_CLASS_AP50_95:
            failures.append({"scope": name, "metric": "ap50_95", "minimum": V2_MIN_PER_CLASS_AP50_95, "actual": ap})
    return failures


def validate_v1_regression(metrics: dict[str, Any]) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    overall = metrics["overall"]
    if float(overall.get("map50_95", 0.0)) < V1_MIN_OVERALL_MAP50_95:
        failures.append({"scope": "overall", "metric": "map50_95", "minimum": V1_MIN_OVERALL_MAP50_95, "actual": overall.get("map50_95")})
    per_class = {str(item.get("source_name")): item for item in metrics.get("per_class", [])}
    for name, minimum in V1_WEAK_CLASS_MIN_AP50_95.items():
        actual = per_class.get(name, {}).get("ap50_95")
        if actual is None or float(actual) < minimum:
            failures.append({"scope": name, "metric": "ap50_95", "minimum": minimum, "actual": actual})
    return failures


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--v2-metrics", type=Path, required=True)
    parser.add_argument("--v1-regression-metrics", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    v2 = load_metrics(args.v2_metrics.resolve())
    v1 = load_metrics(args.v1_regression_metrics.resolve())
    v2_failures = validate_v2(v2)
    v1_failures = validate_v1_regression(v1)
    payload = {
        "schema_version": 1,
        "v2_metrics": str(args.v2_metrics.resolve()),
        "v1_regression_metrics": str(args.v1_regression_metrics.resolve()),
        "v2_thresholds": {
            "overall_map50_95_minimum": V2_MIN_OVERALL_MAP50_95,
            "per_class_recall_at_0.25_minimum": V2_MIN_PER_CLASS_RECALL,
            "per_class_ap50_95_minimum": V2_MIN_PER_CLASS_AP50_95,
            "p95_ms_maximum": V2_MAX_P95_MS,
        },
        "v1_regression_thresholds": {
            "overall_map50_95_minimum": V1_MIN_OVERALL_MAP50_95,
            "weak_class_ap50_95_minimum": V1_WEAK_CLASS_MIN_AP50_95,
        },
        "v2_failures": v2_failures,
        "v1_regression_failures": v1_failures,
        "accepted": not v2_failures and not v1_failures,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    if not payload["accepted"]:
        raise SystemExit("V2 未达到逐类质量或 V1 回归门槛")


if __name__ == "__main__":
    main()
