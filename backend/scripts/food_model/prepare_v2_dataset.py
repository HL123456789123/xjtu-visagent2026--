#!/usr/bin/env python3
"""构建食品识别 V2 数据集，保留 V1 测试集为只读回归基准。

V2 仅复用 V1 的 train/val 源图组，并接收人工新增的 beef/carrot 图片；V1 test
目录从不读取，因此不能被用于选类、调参或早停。新增数据使用下面的扁平 YOLO 目录：

``supplement_root/images/<image>``
``supplement_root/labels/<image-stem>.txt``

图片文件名以 ``_jpg.rf.`` 前缀（或完整 stem）作为独立拍摄源 ID。预检会生成所有
新增框的 100% 审核表；只有审核表每一行都标记为 ``pass`` 且源图数量达标时才会生成
最终 ``food12_v2``。脚本不会写入 V1 数据目录。
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any

import yaml

from prepare_dataset import (
    IMAGE_EXTENSIONS,
    SPLITS,
    ImageRecord,
    canonicalize_records,
    assign_group_splits,
    parse_labels,
    sha256_file,
    source_id_from_filename,
    write_dataset,
    write_json,
)


MIN_SUPPLEMENT_SOURCE_GROUPS = 150
MIN_FINAL_SOURCE_GROUPS = {"train": 200, "val": 25, "test": 25}
WEAK_CLASS_NAMES = ("beef", "carrot")


def load_names(data_yaml: Path) -> list[str]:
    payload = yaml.safe_load(data_yaml.read_text(encoding="utf-8")) or {}
    names = payload.get("names")
    if isinstance(names, dict):
        return [str(names[index]) for index in sorted(names, key=lambda value: int(value))]
    if isinstance(names, list):
        return [str(value) for value in names]
    raise ValueError(f"{data_yaml} 缺少 names")


def load_base_records(base_root: Path, class_names: list[str]) -> list[ImageRecord]:
    """仅加载 V1 train/val，并使用清单中的组 ID，而非重新解析增强文件名。"""
    manifest_path = base_root / "manifest.jsonl"
    if not manifest_path.is_file():
        raise FileNotFoundError(f"V1 数据集缺少 manifest: {manifest_path}")
    source_by_filename: dict[str, str] = {}
    for line in manifest_path.read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        source_by_filename[str(row["filename"])] = str(row["source_id"])

    records: list[ImageRecord] = []
    for split in ("train", "val"):
        image_dir = base_root / split / "images"
        label_dir = base_root / split / "labels"
        if not image_dir.is_dir() or not label_dir.is_dir():
            raise FileNotFoundError(f"V1 缺少 {split} 图片或标签目录")
        for image_path in sorted(image_dir.iterdir()):
            if not image_path.is_file() or image_path.suffix.lower() not in IMAGE_EXTENSIONS:
                continue
            label_path = label_dir / f"{image_path.stem}.txt"
            if not label_path.is_file():
                raise FileNotFoundError(f"V1 图片缺少标签: {image_path}")
            source_id = source_by_filename.get(image_path.name)
            if source_id is None:
                raise ValueError(f"V1 manifest 缺少图片: {image_path.name}")
            records.append(
                ImageRecord(
                    image_path=image_path.resolve(),
                    label_path=label_path.resolve(),
                    source_split=f"v1_{split}",
                    source_id=f"v1:{source_id}",
                    sha256=sha256_file(image_path),
                    labels=parse_labels(label_path, len(class_names)),
                )
            )
    if not records:
        raise ValueError("V1 train/val 没有可用图片")
    return records


def load_supplement_records(supplement_root: Path, class_names: list[str]) -> list[ImageRecord]:
    """读取扁平补充集，并拒绝未包含弱类的图片，避免用无关数据凑数量。"""
    image_dir = supplement_root / "images"
    label_dir = supplement_root / "labels"
    if not image_dir.is_dir() or not label_dir.is_dir():
        return []
    weak_ids = {class_names.index(name) for name in WEAK_CLASS_NAMES}
    records: list[ImageRecord] = []
    image_paths = sorted(
        path for path in image_dir.iterdir() if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
    )
    for image_path in image_paths:
        label_path = label_dir / f"{image_path.stem}.txt"
        if not label_path.is_file():
            raise FileNotFoundError(f"补充图片缺少标签: {image_path}")
        labels = parse_labels(label_path, len(class_names))
        if not labels or not any(label.class_id in weak_ids for label in labels):
            raise ValueError(f"补充图片必须至少标注 beef 或 carrot: {image_path}")
        records.append(
            ImageRecord(
                image_path=image_path.resolve(),
                label_path=label_path.resolve(),
                source_split="supplement",
                source_id=f"supplement:{source_id_from_filename(image_path.name)}",
                sha256=sha256_file(image_path),
                labels=labels,
            )
        )
    orphan_labels = {path.stem for path in label_dir.glob("*.txt")} - {path.stem for path in image_paths}
    if orphan_labels:
        raise ValueError(f"补充集存在孤立标签，示例: {sorted(orphan_labels)[0]}")
    return records


def class_group_coverage(
    records: list[ImageRecord],
    source_groups: dict[str, str],
    assignments: dict[str, str],
    class_names: list[str],
) -> dict[str, dict[str, int]]:
    groups: dict[str, dict[int, set[str]]] = {
        split: {class_id: set() for class_id in range(len(class_names))} for split in SPLITS
    }
    for record in records:
        group = source_groups[record.source_id]
        split = assignments[group]
        for label in record.labels:
            groups[split][label.class_id].add(group)
    return {
        split: {class_names[class_id]: len(values) for class_id, values in per_class.items()}
        for split, per_class in groups.items()
    }


def supplement_group_counts(
    records: list[ImageRecord], source_groups: dict[str, str], class_names: list[str]
) -> dict[str, int]:
    weak_ids = {name: class_names.index(name) for name in WEAK_CLASS_NAMES}
    groups = {name: set() for name in WEAK_CLASS_NAMES}
    for record in records:
        if not record.source_id.startswith("supplement:"):
            continue
        group = source_groups[record.source_id]
        for class_name, class_id in weak_ids.items():
            if any(label.class_id == class_id for label in record.labels):
                groups[class_name].add(group)
    return {name: len(values) for name, values in groups.items()}


def write_audit(path: Path, records: list[ImageRecord], source_groups: dict[str, str], class_names: list[str]) -> int:
    rows: list[dict[str, Any]] = []
    for record in sorted(records, key=lambda item: str(item.image_path)):
        if not record.source_id.startswith("supplement:"):
            continue
        for box_index, label in enumerate(record.labels, start=1):
            rows.append(
                {
                    "source_group": source_groups[record.source_id],
                    "image_path": str(record.image_path),
                    "box_index": box_index,
                    "class_id": label.class_id,
                    "class_name": class_names[label.class_id],
                    "bbox_yolo": label.as_line(),
                    "review_status": "pending",
                    "review_note": "",
                }
            )
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]) if rows else [
            "source_group", "image_path", "box_index", "class_id", "class_name", "bbox_yolo", "review_status", "review_note"
        ])
        writer.writeheader()
        writer.writerows(rows)
    return len(rows)


def validate_audit(audit_path: Path, expected_boxes: int) -> None:
    if not audit_path.is_file():
        raise FileNotFoundError(f"缺少新增数据 100% 审核文件: {audit_path}")
    with audit_path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if len(rows) != expected_boxes:
        raise ValueError(f"审核行数不匹配: 期望 {expected_boxes}，实际 {len(rows)}")
    invalid = [row for row in rows if row.get("review_status", "").strip().lower() != "pass"]
    if invalid:
        raise ValueError(f"新增数据必须 100% 审核通过，当前未通过/未审核框数: {len(invalid)}")


def preflight(args: argparse.Namespace) -> dict[str, Any]:
    class_names = load_names(args.base_root / "data.yaml")
    if WEAK_CLASS_NAMES[0] not in class_names or WEAK_CLASS_NAMES[1] not in class_names:
        raise ValueError("V1 类别映射缺少 beef 或 carrot")
    base_records = load_base_records(args.base_root, class_names)
    supplement_exists = (args.supplement_root / "images").is_dir() and (args.supplement_root / "labels").is_dir()
    supplement_records = load_supplement_records(args.supplement_root, class_names) if supplement_exists else []
    base_hashes = {record.sha256 for record in base_records}
    supplement_duplicate_hashes = sorted({record.sha256 for record in supplement_records if record.sha256 in base_hashes})
    canonical_records, source_groups, duplicate_issues = canonicalize_records(base_records + supplement_records)
    counts = supplement_group_counts(canonical_records, source_groups, class_names)
    audit_path = args.report_root / "supplement_audit_100pct.csv"
    audit_boxes = write_audit(audit_path, canonical_records, source_groups, class_names)
    unmet = {
        class_name: max(0, MIN_SUPPLEMENT_SOURCE_GROUPS - count)
        for class_name, count in counts.items()
    }
    result = {
        "schema_version": 1,
        "base_dataset": str(args.base_root),
        "v1_test_read": False,
        "supplement_root": str(args.supplement_root),
        "supplement_root_exists": supplement_exists,
        "canonical_v1_train_val_images": len([r for r in canonical_records if r.source_id.startswith("v1:")]),
        "canonical_supplement_images": len([r for r in canonical_records if r.source_id.startswith("supplement:")]),
        "supplement_source_groups": counts,
        "minimum_supplement_source_groups": MIN_SUPPLEMENT_SOURCE_GROUPS,
        "supplement_source_group_gap": unmet,
        "supplement_duplicate_hashes_already_in_v1_train_val": supplement_duplicate_hashes,
        "duplicate_label_conflicts": duplicate_issues,
        "audit_file": str(audit_path),
        "audit_boxes": audit_boxes,
        "requirements_met": (
            supplement_exists
            and not supplement_duplicate_hashes
            and not duplicate_issues
            and all(value == 0 for value in unmet.values())
        ),
    }
    write_json(args.report_root / "v2_preflight.json", result)
    return result


def build(args: argparse.Namespace) -> None:
    result = preflight(args)
    if not result["requirements_met"]:
        raise ValueError("V2 补充数据未满足源图组/重复冲突要求；请查看 v2_preflight.json")
    class_names = load_names(args.base_root / "data.yaml")
    base_records = load_base_records(args.base_root, class_names)
    supplement_records = load_supplement_records(args.supplement_root, class_names)
    if {record.sha256 for record in supplement_records} & {record.sha256 for record in base_records}:
        raise ValueError("补充集包含已在 V1 train/val 出现的精确重复图片，拒绝构建 V2")
    records, source_groups, duplicate_issues = canonicalize_records(base_records + supplement_records)
    if duplicate_issues:
        raise ValueError("存在标签不一致的精确重复图，拒绝构建 V2")
    expected_audit_boxes = sum(len(record.labels) for record in records if record.source_id.startswith("supplement:"))
    validate_audit(args.audit_file, expected_audit_boxes)
    assignments = assign_group_splits(records, source_groups, len(class_names), args.seed)
    coverage = class_group_coverage(records, source_groups, assignments, class_names)
    coverage_failures = [
        f"{name}:{split}={coverage[split][name]}<{minimum}"
        for name in WEAK_CLASS_NAMES
        for split, minimum in MIN_FINAL_SOURCE_GROUPS.items()
        if coverage[split][name] < minimum
    ]
    if coverage_failures:
        raise ValueError("V2 分层后弱类源图覆盖不足: " + ", ".join(coverage_failures))
    metadata = write_dataset(
        records=records,
        source_groups=source_groups,
        assignments=assignments,
        output_root=args.output_root,
        class_names=class_names,
        selected_source_ids=None,
        overwrite=args.overwrite,
    )
    version = {
        "schema_version": 2,
        "seed": args.seed,
        "base_dataset": str(args.base_root),
        "v1_test_read": False,
        "supplement_root": str(args.supplement_root),
        "v2_source_coverage": coverage,
        "minimum_final_source_groups": MIN_FINAL_SOURCE_GROUPS,
        "supplement_source_groups": supplement_group_counts(records, source_groups, class_names),
        "duplicate_label_conflicts": 0,
        "audit_file": str(args.audit_file),
        "dataset_metadata": metadata,
    }
    write_json(args.report_root / "v2_build.json", version)
    print(json.dumps({"dataset": str(args.output_root), **version}, ensure_ascii=False, indent=2))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("preflight", "build"), required=True)
    parser.add_argument("--base-root", type=Path, default=Path("/root/autodl-tmp/visagent/datasets/food12_grouped"))
    parser.add_argument("--supplement-root", type=Path, default=Path("/root/autodl-tmp/visagent/datasets/food12_v2_supplement"))
    parser.add_argument("--output-root", type=Path, default=Path("/root/autodl-tmp/visagent/datasets/food12_v2"))
    parser.add_argument("--report-root", type=Path, default=Path("/root/autodl-tmp/visagent/reports/food/v2/data"))
    parser.add_argument("--audit-file", type=Path)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--overwrite", action="store_true")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    args.base_root = args.base_root.resolve()
    args.supplement_root = args.supplement_root.resolve()
    args.output_root = args.output_root.resolve()
    args.report_root = args.report_root.resolve()
    if args.mode == "preflight":
        print(json.dumps(preflight(args), ensure_ascii=False, indent=2))
        return
    if args.audit_file is None:
        raise SystemExit("--mode build 必须传入已完成的 --audit-file")
    args.audit_file = args.audit_file.resolve()
    build(args)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"V2 数据构建失败: {exc}", file=sys.stderr)
        raise
