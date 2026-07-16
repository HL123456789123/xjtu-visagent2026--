#!/usr/bin/env python3
"""验证冠军权重、最终数据集和 V1 类别映射严格同序。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import yaml
from ultralytics import YOLO


def ordered_names(raw: object) -> list[str]:
    if isinstance(raw, list):
        return [str(value) for value in raw]
    if isinstance(raw, dict):
        return [str(raw[index]) for index in sorted(raw, key=lambda value: int(value))]
    raise ValueError("类别定义必须为 list 或连续 ID 映射")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--weights", type=Path, required=True)
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--classes", type=Path, required=True)
    args = parser.parse_args()
    data = yaml.safe_load(args.data.read_text(encoding="utf-8")) or {}
    class_file = yaml.safe_load(args.classes.read_text(encoding="utf-8")) or {}
    data_names = ordered_names(data.get("names"))
    raw_definitions = class_file.get("names")
    if not isinstance(raw_definitions, dict):
        raise ValueError("classes.yaml 的 names 必须是映射")
    class_names = []
    for class_id in range(len(raw_definitions)):
        definition = raw_definitions.get(class_id, raw_definitions.get(str(class_id)))
        if not isinstance(definition, dict) or not definition.get("class_name") or not definition.get("display_name"):
            raise ValueError(f"classes.yaml 缺少连续 ID {class_id} 的 class_name/display_name")
        class_names.append(str(definition["class_name"]))
    if len(raw_definitions) != len(class_names):
        raise ValueError("classes.yaml ID 必须从 0 开始连续且不重复")
    model = YOLO(str(args.weights.resolve()))
    model_names = ordered_names(model.names)
    result = {
        "weights": str(args.weights.resolve()),
        "data_names": data_names,
        "classes_yaml_names": class_names,
        "weight_metadata_names": model_names,
        "class_count": len(class_names),
    }
    if not (data_names == class_names == model_names):
        raise ValueError(json.dumps(result, ensure_ascii=False, indent=2))
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
