#!/usr/bin/env python3
"""独立验证派生 YOLO 数据集，拒绝带泄漏或损坏标注进入训练。"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict
from pathlib import Path

import yaml
from PIL import Image


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
SPLITS = ("train", "val", "test")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_names(data_yaml: Path) -> list[str]:
    payload = yaml.safe_load(data_yaml.read_text(encoding="utf-8")) or {}
    names = payload.get("names")
    if isinstance(names, dict):
        return [str(names[index]) for index in sorted(names, key=lambda value: int(value))]
    if isinstance(names, list):
        return [str(item) for item in names]
    raise ValueError(f"{data_yaml} 缺少 names")


def validate_label(path: Path, num_classes: int) -> int:
    boxes = 0
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        fields = line.split()
        if not fields:
            continue
        if len(fields) != 5:
            raise ValueError(f"{path}:{line_number} 不是 5 列 YOLO 标注")
        class_id = int(fields[0])
        x, y, width, height = (float(value) for value in fields[1:])
        if not 0 <= class_id < num_classes:
            raise ValueError(f"{path}:{line_number} 类别 ID 越界")
        if not (0 <= x <= 1 and 0 <= y <= 1 and 0 < width <= 1 and 0 < height <= 1):
            raise ValueError(f"{path}:{line_number} bbox 数值越界")
        if x - width / 2 < -1e-6 or y - height / 2 < -1e-6 or x + width / 2 > 1 + 1e-6 or y + height / 2 > 1 + 1e-6:
            raise ValueError(f"{path}:{line_number} bbox 超出图像边界")
        boxes += 1
    return boxes


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, required=True, help="派生数据集 data.yaml")
    args = parser.parse_args()
    data_yaml = args.data.resolve()
    names = load_names(data_yaml)
    payload = yaml.safe_load(data_yaml.read_text(encoding="utf-8")) or {}
    root = Path(payload.get("path", data_yaml.parent)).resolve()

    image_hashes: dict[str, set[str]] = defaultdict(set)
    source_splits: dict[str, set[str]] = defaultdict(set)
    summary: dict[str, dict[str, int]] = {}
    for split in SPLITS:
        image_dir = root / split / "images"
        label_dir = root / split / "labels"
        images = sorted(path for path in image_dir.iterdir() if path.suffix.lower() in IMAGE_EXTENSIONS)
        labels = {path.stem: path for path in label_dir.glob("*.txt")}
        image_stems = {path.stem for path in images}
        if image_stems != set(labels):
            raise ValueError(f"{split} 图片/标签不配对: images={len(image_stems)}, labels={len(labels)}")
        box_count = 0
        for image_path in images:
            with Image.open(image_path) as image:
                image.verify()
            box_count += validate_label(labels[image_path.stem], len(names))
            image_hashes[sha256_file(image_path)].add(split)
        summary[split] = {"images": len(images), "boxes": box_count}

    cross_split_duplicate_hashes = sum(len(splits) > 1 for splits in image_hashes.values())
    manifest = root / "manifest.jsonl"
    if not manifest.is_file():
        raise FileNotFoundError(f"缺少分组清单: {manifest}")
    for line in manifest.read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        source_splits[str(row["source_id"])].add(str(row["output_split"]))
    cross_split_source_groups = sum(len(splits) > 1 for splits in source_splits.values())
    result = {
        "dataset": str(root),
        "classes": len(names),
        "splits": summary,
        "exact_duplicate_hashes_cross_split": cross_split_duplicate_hashes,
        "source_groups_cross_split": cross_split_source_groups,
    }
    if cross_split_duplicate_hashes or cross_split_source_groups:
        raise ValueError(json.dumps(result, ensure_ascii=False))
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
