#!/usr/bin/env python3
"""构建无源图泄漏的食品 YOLO 数据集。

原始 Roboflow 导出把同一张冰箱照片的多个增强版本拆散到了 train/valid/test。
本脚本以 ``_jpg.rf.`` 前的源图编号为分组键，并额外使用 SHA-256 把完全相同的
图片合并为同一组。它提供两个阶段：

* ``prepare30``：生成无泄漏的 30 类基线数据集和人工标注审计清单；
* ``build12``：读取评估脚本生成的严格选择文件，筛选并重映射为最终 12 类数据集。

所有派生数据都在仓库外的 ``/root/autodl-tmp/visagent`` 中生成，原始数据不会被
修改。重复图像的标签不一致时，整组图片会被排除并写入报告，而不会静默选其中一份。
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import random
import shutil
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import yaml

from catalog import SOURCE_NAMES, output_definition


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
SPLITS = ("train", "val", "test")
SPLIT_RATIOS = {"train": 0.80, "val": 0.10, "test": 0.10}


@dataclass(frozen=True)
class Label:
    """YOLO 格式中的一个合法标注框。"""

    class_id: int
    x_center: float
    y_center: float
    width: float
    height: float

    def as_line(self, class_id: int | None = None) -> str:
        """以稳定精度写回 YOLO TXT 行。"""
        target_id = self.class_id if class_id is None else class_id
        return (
            f"{target_id} {self.x_center:.8f} {self.y_center:.8f} "
            f"{self.width:.8f} {self.height:.8f}"
        )


@dataclass(frozen=True)
class ImageRecord:
    """原始图像、标注和数据来源信息。"""

    image_path: Path
    label_path: Path
    source_split: str
    source_id: str
    sha256: str
    labels: tuple[Label, ...]

    @property
    def filename(self) -> str:
        return self.image_path.name


class UnionFind:
    """用于把完全重复图片涉及的多个 source_id 合并。"""

    def __init__(self, values: Iterable[str]):
        self.parent = {value: value for value in values}

    def find(self, value: str) -> str:
        parent = self.parent[value]
        if parent != value:
            self.parent[value] = self.find(parent)
        return self.parent[value]

    def union(self, left: str, right: str) -> None:
        left_root = self.find(left)
        right_root = self.find(right)
        if left_root == right_root:
            return
        if left_root < right_root:
            self.parent[right_root] = left_root
        else:
            self.parent[left_root] = right_root


def source_id_from_filename(filename: str) -> str:
    """取得 Roboflow 文件名中增强前的稳定源图编号。"""
    marker = "_jpg.rf."
    if marker in filename:
        return filename.split(marker, 1)[0]
    return Path(filename).stem


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_labels(path: Path, num_classes: int) -> tuple[Label, ...]:
    """读取并严格校验一个 YOLO TXT 标注文件。"""
    labels: list[Label] = []
    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) != 5:
            raise ValueError(f"{path}:{line_number} 必须包含 5 列，实际为 {len(parts)} 列")
        try:
            class_id = int(parts[0])
            x_center, y_center, width, height = (float(value) for value in parts[1:])
        except ValueError as exc:
            raise ValueError(f"{path}:{line_number} 包含非数值字段") from exc
        if not 0 <= class_id < num_classes:
            raise ValueError(f"{path}:{line_number} 类别 {class_id} 不在 0..{num_classes - 1}")
        if not (0 <= x_center <= 1 and 0 <= y_center <= 1 and 0 < width <= 1 and 0 < height <= 1):
            raise ValueError(f"{path}:{line_number} 的 YOLO 坐标不合法")
        if x_center - width / 2 < -1e-6 or y_center - height / 2 < -1e-6:
            raise ValueError(f"{path}:{line_number} 边界框越出图像左侧或上侧")
        if x_center + width / 2 > 1 + 1e-6 or y_center + height / 2 > 1 + 1e-6:
            raise ValueError(f"{path}:{line_number} 边界框越出图像右侧或下侧")
        labels.append(Label(class_id, x_center, y_center, width, height))
    return tuple(labels)


def label_signature(labels: tuple[Label, ...]) -> tuple[tuple[int, float, float, float, float], ...]:
    """忽略文本行顺序后比较重复图的标注是否一致。"""
    return tuple(
        sorted(
            (
                label.class_id,
                round(label.x_center, 8),
                round(label.y_center, 8),
                round(label.width, 8),
                round(label.height, 8),
            )
            for label in labels
        )
    )


def load_source_names(data_yaml: Path) -> list[str]:
    payload = yaml.safe_load(data_yaml.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"无效 data.yaml: {data_yaml}")
    raw_names = payload.get("names")
    if isinstance(raw_names, dict):
        names = [raw_names[index] for index in sorted(raw_names, key=lambda value: int(value))]
    elif isinstance(raw_names, list):
        names = raw_names
    else:
        raise ValueError(f"{data_yaml} 缺少 names")
    names = [str(name) for name in names]
    if names != SOURCE_NAMES:
        raise ValueError(
            "原始类别顺序与 food_model/catalog.py 不一致。"
            f"\nYAML: {names}\n期望: {SOURCE_NAMES}"
        )
    return names


def scan_source_dataset(input_root: Path, source_names: list[str]) -> list[ImageRecord]:
    """扫描原始数据，并在任何格式问题上失败，避免训练静默吞掉坏标注。"""
    records: list[ImageRecord] = []
    split_directory = {"train": "train", "val": "valid", "test": "test"}
    for output_split, input_split in split_directory.items():
        images_dir = input_root / input_split / "images"
        labels_dir = input_root / input_split / "labels"
        if not images_dir.is_dir() or not labels_dir.is_dir():
            raise FileNotFoundError(f"缺少原始数据目录: {images_dir} 或 {labels_dir}")
        image_paths = sorted(
            path for path in images_dir.iterdir() if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
        )
        for image_path in image_paths:
            label_path = labels_dir / f"{image_path.stem}.txt"
            if not label_path.is_file():
                raise FileNotFoundError(f"图片没有对应标注: {image_path}")
            labels = parse_labels(label_path, len(source_names))
            records.append(
                ImageRecord(
                    image_path=image_path.resolve(),
                    label_path=label_path.resolve(),
                    source_split=output_split,
                    source_id=source_id_from_filename(image_path.name),
                    sha256=sha256_file(image_path),
                    labels=labels,
                )
            )
        orphan_labels = {path.stem for path in labels_dir.glob("*.txt")} - {path.stem for path in image_paths}
        if orphan_labels:
            example = sorted(orphan_labels)[0]
            raise ValueError(f"发现没有图片的标注，示例: {labels_dir / (example + '.txt')}")
    if not records:
        raise ValueError(f"没有在 {input_root} 找到图片")
    return records


def canonicalize_records(records: list[ImageRecord]) -> tuple[list[ImageRecord], dict[str, str], list[dict[str, Any]]]:
    """按哈希去重、合并来源组并记录标签冲突。"""
    groups_by_hash: dict[str, list[ImageRecord]] = defaultdict(list)
    for record in records:
        groups_by_hash[record.sha256].append(record)

    union_find = UnionFind(record.source_id for record in records)
    for duplicate_group in groups_by_hash.values():
        root_source = duplicate_group[0].source_id
        for record in duplicate_group[1:]:
            union_find.union(root_source, record.source_id)

    canonical_records: list[ImageRecord] = []
    issues: list[dict[str, Any]] = []
    for sha256, duplicate_group in sorted(groups_by_hash.items()):
        signatures = {label_signature(record.labels) for record in duplicate_group}
        if len(signatures) > 1:
            issues.append(
                {
                    "issue": "duplicate_images_have_different_labels",
                    "sha256": sha256,
                    "files": [str(record.image_path) for record in sorted(duplicate_group, key=lambda item: str(item.image_path))],
                }
            )
            continue
        keep = min(duplicate_group, key=lambda item: (item.source_id, str(item.image_path)))
        canonical_records.append(keep)

    source_groups = {source_id: union_find.find(source_id) for source_id in union_find.parent}
    return canonical_records, source_groups, issues


def record_class_counts(record: ImageRecord, num_classes: int) -> list[int]:
    counts = [0] * num_classes
    for label in record.labels:
        counts[label.class_id] += 1
    return counts


def assign_group_splits(
    records: list[ImageRecord], source_groups: dict[str, str], num_classes: int, seed: int
) -> dict[str, str]:
    """按源图组做确定性的多标签贪心分层划分。"""
    grouped: dict[str, list[ImageRecord]] = defaultdict(list)
    for record in records:
        grouped[source_groups[record.source_id]].append(record)
    if len(grouped) < 30:
        raise ValueError("源图组数量过少，无法稳定划分 train/val/test")

    group_vectors: dict[str, list[int]] = {}
    global_counts = [0] * num_classes
    for group_id, group_records in grouped.items():
        vector = [0] * num_classes
        for record in group_records:
            counts = record_class_counts(record, num_classes)
            vector = [left + right for left, right in zip(vector, counts)]
        group_vectors[group_id] = vector
        global_counts = [left + right for left, right in zip(global_counts, vector)]

    total_images = sum(len(group_records) for group_records in grouped.values())
    target_images = {
        "train": round(total_images * SPLIT_RATIOS["train"]),
        "val": round(total_images * SPLIT_RATIOS["val"]),
    }
    target_images["test"] = total_images - target_images["train"] - target_images["val"]
    target_counts = {
        split: [count * SPLIT_RATIOS[split] for count in global_counts] for split in SPLITS
    }
    assigned_counts = {split: [0] * num_classes for split in SPLITS}
    assigned_images = Counter()
    assignments: dict[str, str] = {}
    tie_rng = random.Random(seed)
    tie_breaker = {group_id: tie_rng.random() for group_id in grouped}

    def rarity(group_id: str) -> tuple[int, float, float, str]:
        vector = group_vectors[group_id]
        score = sum(value / math.sqrt(global_counts[index] + 1) for index, value in enumerate(vector) if value)
        # 先安置 8 张增强图这样的大组，配合硬图像配额可使 80/10/10 保持精确；
        # 同一大小内再优先处理稀有多标签组，才是实际的多标签分层步骤。
        return (-len(grouped[group_id]), -score, tie_breaker[group_id], group_id)

    for group_id in sorted(grouped, key=rarity):
        vector = group_vectors[group_id]
        candidates = [
            split
            for split in SPLITS
            if assigned_images[split] + len(grouped[group_id]) <= target_images[split]
        ]
        if not candidates:
            # 仅会在某个源图组大于剩余槽位时触发。保留可重复的最小溢出选择，
            # 之后的验证会把实际比例写入报告而不会掩盖偏差。
            candidates = list(SPLITS)

        def cost(split: str) -> tuple[float, str]:
            projected = [left + right for left, right in zip(assigned_counts[split], vector)]
            label_error = sum(
                ((projected[index] - target_counts[split][index]) / max(target_counts[split][index], 1)) ** 2
                for index, value in enumerate(vector)
                if value
            )
            projected_images = assigned_images[split] + len(grouped[group_id])
            image_error = ((projected_images - target_images[split]) / max(target_images[split], 1)) ** 2
            overflow = max(0, projected_images - target_images[split]) / max(target_images[split], 1)
            # 图片比例是不可退让的主约束；在同等容量下以多标签误差作分层选择。
            return (label_error * 0.1 + image_error + overflow * overflow * num_classes * 5, split)

        selected_split = min(candidates, key=cost)
        assignments[group_id] = selected_split
        assigned_images[selected_split] += len(grouped[group_id])
        assigned_counts[selected_split] = [
            left + right for left, right in zip(assigned_counts[selected_split], vector)
        ]

    return assignments


def validate_source_coverage(
    records: list[ImageRecord], source_groups: dict[str, str], assignments: dict[str, str], num_classes: int
) -> dict[str, dict[int, int]]:
    """验证重划分后每类由多少独立源图支持，并返回统计。"""
    coverage: dict[str, dict[int, set[str]]] = {
        split: {class_id: set() for class_id in range(num_classes)} for split in SPLITS
    }
    for record in records:
        split = assignments[source_groups[record.source_id]]
        group_id = source_groups[record.source_id]
        for label in record.labels:
            coverage[split][label.class_id].add(group_id)
    result = {
        split: {class_id: len(groups) for class_id, groups in class_groups.items()}
        for split, class_groups in coverage.items()
    }
    missing = [
        f"{SOURCE_NAMES[class_id]}:{split}={result[split][class_id]}"
        for class_id in range(num_classes)
        for split in SPLITS
        if result[split][class_id] == 0
    ]
    if missing:
        raise ValueError("分层划分使类别在某集合中缺失: " + ", ".join(missing))
    return result


def hardlink_or_copy(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.link(source, destination)
    except OSError:
        shutil.copy2(source, destination)


def make_empty_directory(path: Path, overwrite: bool) -> None:
    if path.exists():
        if not overwrite:
            raise FileExistsError(f"输出目录已存在: {path}；如确认可删除，请传入 --overwrite")
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=False)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, records: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_dataset(
    *,
    records: list[ImageRecord],
    source_groups: dict[str, str],
    assignments: dict[str, str],
    output_root: Path,
    class_names: list[str],
    selected_source_ids: list[int] | None,
    overwrite: bool,
) -> dict[str, Any]:
    """以硬链接优先的方式构建 YOLO 数据集，并在 12 类模式下重映射标签。"""
    make_empty_directory(output_root, overwrite)
    source_to_target = (
        {source_id: source_id for source_id in range(len(class_names))}
        if selected_source_ids is None
        else {source_id: target_id for target_id, source_id in enumerate(selected_source_ids)}
    )
    included = Counter()
    excluded_without_selected = 0
    class_instances = {split: Counter() for split in SPLITS}
    manifest_rows: list[dict[str, Any]] = []

    for record in sorted(records, key=lambda item: str(item.image_path)):
        split = assignments[source_groups[record.source_id]]
        filtered = [label for label in record.labels if label.class_id in source_to_target]
        if selected_source_ids is not None and not filtered:
            excluded_without_selected += 1
            continue
        image_destination = output_root / split / "images" / record.filename
        label_destination = output_root / split / "labels" / f"{record.image_path.stem}.txt"
        hardlink_or_copy(record.image_path, image_destination)
        label_destination.parent.mkdir(parents=True, exist_ok=True)
        label_destination.write_text(
            "\n".join(label.as_line(source_to_target[label.class_id]) for label in filtered) + "\n",
            encoding="utf-8",
        )
        included[split] += 1
        for label in filtered:
            class_instances[split][source_to_target[label.class_id]] += 1
        manifest_rows.append(
            {
                "image_path": str(record.image_path),
                "label_path": str(record.label_path),
                "output_split": split,
                "source_id": source_groups[record.source_id],
                "original_source_id": record.source_id,
                "sha256": record.sha256,
                "filename": record.filename,
            }
        )

    dataset_yaml = {
        "path": str(output_root.resolve()),
        "train": "train/images",
        "val": "val/images",
        "test": "test/images",
        "nc": len(class_names),
        "names": class_names,
    }
    (output_root / "data.yaml").write_text(
        yaml.safe_dump(dataset_yaml, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )
    write_jsonl(output_root / "manifest.jsonl", manifest_rows)
    metadata = {
        "schema_version": 1,
        "class_names": class_names,
        "selected_source_ids": selected_source_ids,
        "split_images": dict(included),
        "split_class_instances": {
            split: {class_names[class_id]: count for class_id, count in sorted(counts.items())}
            for split, counts in class_instances.items()
        },
        "excluded_without_selected_class": excluded_without_selected,
    }
    write_json(output_root / "dataset_metadata.json", metadata)
    return metadata


def write_reports(
    *,
    report_root: Path,
    records: list[ImageRecord],
    source_groups: dict[str, str],
    assignments: dict[str, str],
    duplicate_issues: list[dict[str, Any]],
    num_classes: int,
    seed: int,
) -> None:
    """写出数据审计、类别分布和人工复核清单。"""
    report_root.mkdir(parents=True, exist_ok=True)
    coverage = validate_source_coverage(records, source_groups, assignments, num_classes)
    write_json(report_root / "duplicate_issues.json", duplicate_issues)
    write_json(
        report_root / "split_report.json",
        {
            "seed": seed,
            "source_groups": len(set(source_groups.values())),
            "canonical_images": len(records),
            "duplicate_label_conflicts_excluded": len(duplicate_issues),
            "class_source_coverage": {
                split: {SOURCE_NAMES[class_id]: count for class_id, count in values.items()}
                for split, values in coverage.items()
            },
            "source_group_overlap": 0,
        },
    )

    distribution: dict[str, Counter[int]] = {split: Counter() for split in SPLITS}
    source_distribution: dict[str, dict[int, set[str]]] = {
        split: defaultdict(set) for split in SPLITS
    }
    for record in records:
        split = assignments[source_groups[record.source_id]]
        group_id = source_groups[record.source_id]
        for label in record.labels:
            distribution[split][label.class_id] += 1
            source_distribution[split][label.class_id].add(group_id)
    with (report_root / "class_distribution.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["class_id", "source_name", "split", "instances", "unique_source_groups"],
        )
        writer.writeheader()
        for class_id, source_name in enumerate(SOURCE_NAMES):
            for split in SPLITS:
                writer.writerow(
                    {
                        "class_id": class_id,
                        "source_name": source_name,
                        "split": split,
                        "instances": distribution[split][class_id],
                        "unique_source_groups": len(source_distribution[split][class_id]),
                    }
                )

    audit_rows: list[dict[str, Any]] = []
    records_by_class_source: dict[int, dict[str, list[tuple[ImageRecord, Label]]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for record in records:
        if assignments[source_groups[record.source_id]] != "train":
            continue
        for label in record.labels:
            records_by_class_source[label.class_id][source_groups[record.source_id]].append((record, label))
    for class_id in range(num_classes):
        candidates: list[tuple[ImageRecord, Label]] = []
        for group_id in sorted(records_by_class_source[class_id]):
            candidates.append(sorted(records_by_class_source[class_id][group_id], key=lambda item: str(item[0].image_path))[0])
        random.Random(seed + class_id).shuffle(candidates)
        for review_index, (record, label) in enumerate(candidates[:30], start=1):
            audit_rows.append(
                {
                    "class_id": class_id,
                    "source_name": SOURCE_NAMES[class_id],
                    "review_index": review_index,
                    "source_group": source_groups[record.source_id],
                    "image_path": str(record.image_path),
                    "bbox_yolo": label.as_line(),
                    "review_status": "pending",
                    "review_note": "",
                }
            )
    with (report_root / "audit_review.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "class_id",
                "source_name",
                "review_index",
                "source_group",
                "image_path",
                "bbox_yolo",
                "review_status",
                "review_note",
            ],
        )
        writer.writeheader()
        writer.writerows(audit_rows)


def prepare30(args: argparse.Namespace) -> None:
    source_names = load_source_names(args.input_root / "data.yaml")
    records = scan_source_dataset(args.input_root, source_names)
    canonical_records, source_groups, duplicate_issues = canonicalize_records(records)
    assignments = assign_group_splits(canonical_records, source_groups, len(source_names), args.seed)
    write_reports(
        report_root=args.report_root,
        records=canonical_records,
        source_groups=source_groups,
        assignments=assignments,
        duplicate_issues=duplicate_issues,
        num_classes=len(source_names),
        seed=args.seed,
    )
    metadata = write_dataset(
        records=canonical_records,
        source_groups=source_groups,
        assignments=assignments,
        output_root=args.output_root,
        class_names=source_names,
        selected_source_ids=None,
        overwrite=args.overwrite,
    )
    print(json.dumps({"dataset": str(args.output_root), **metadata}, ensure_ascii=False, indent=2))


def strict_selection(selection_file: Path) -> tuple[list[int], list[str]]:
    payload = json.loads(selection_file.read_text(encoding="utf-8"))
    if not payload.get("strict_audit_passed"):
        raise ValueError("选择文件未通过严格人工标注审计，拒绝构建最终 12 类数据集")
    selected = payload.get("selected_classes")
    if not isinstance(selected, list) or len(selected) != 12:
        raise ValueError("选择文件必须恰好包含 12 个 selected_classes")
    selected_ids: list[int] = []
    output_names: list[str] = []
    for item in selected:
        source_name = item.get("source_name") if isinstance(item, dict) else None
        if source_name not in SOURCE_NAMES:
            raise ValueError(f"选择文件包含未知类别: {source_name}")
        source_id = SOURCE_NAMES.index(source_name)
        if source_id in selected_ids:
            raise ValueError(f"选择文件包含重复类别: {source_name}")
        selected_ids.append(source_id)
        expected = output_definition(source_name).class_name
        if item.get("class_name") != expected:
            raise ValueError(f"{source_name} 的 class_name 必须为 {expected}")
        output_names.append(expected)
    return selected_ids, output_names


def build12(args: argparse.Namespace) -> None:
    selected_ids, output_names = strict_selection(args.selection_file)
    source_names = load_source_names(args.input_root / "data.yaml")
    records = scan_source_dataset(args.input_root, source_names)
    canonical_records, source_groups, duplicate_issues = canonicalize_records(records)
    if duplicate_issues:
        print(
            f"警告：排除了 {len(duplicate_issues)} 组标签冲突的完全重复图像；详情见 30 类报告。",
            file=sys.stderr,
        )
    assignments = assign_group_splits(canonical_records, source_groups, len(source_names), args.seed)
    metadata = write_dataset(
        records=canonical_records,
        source_groups=source_groups,
        assignments=assignments,
        output_root=args.output_root,
        class_names=output_names,
        selected_source_ids=selected_ids,
        overwrite=args.overwrite,
    )
    classes_yaml = {
        "names": {
            target_id: {
                "class_name": output_definition(SOURCE_NAMES[source_id]).class_name,
                "display_name": output_definition(SOURCE_NAMES[source_id]).display_name,
            }
            for target_id, source_id in enumerate(selected_ids)
        }
    }
    args.classes_output.parent.mkdir(parents=True, exist_ok=True)
    args.classes_output.write_text(
        yaml.safe_dump(classes_yaml, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )
    write_json(
        args.report_root / "final_class_mapping.json",
        {
            "selected_source_ids": selected_ids,
            "selected_source_names": [SOURCE_NAMES[index] for index in selected_ids],
            "output_class_names": output_names,
            "classes_yaml": str(args.classes_output),
        },
    )
    print(json.dumps({"dataset": str(args.output_root), "classes": output_names, **metadata}, ensure_ascii=False, indent=2))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("prepare30", "build12"), required=True)
    parser.add_argument(
        "--input-root",
        type=Path,
        default=Path("/root/autodl-tmp/visagent/datasets/fridge_original_v1"),
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=Path("/root/autodl-tmp/visagent/datasets/food30_grouped"),
    )
    parser.add_argument(
        "--report-root",
        type=Path,
        default=Path("/root/autodl-tmp/visagent/reports/food/data"),
    )
    parser.add_argument("--selection-file", type=Path, help="evaluate.py 生成的严格 12 类选择文件")
    parser.add_argument(
        "--classes-output",
        type=Path,
        default=Path("backend/scripts/food_model/classes.yaml"),
    )
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--overwrite", action="store_true", help="允许删除指定输出目录后重建")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.input_root = args.input_root.resolve()
    args.output_root = args.output_root.resolve()
    args.report_root = args.report_root.resolve()
    args.classes_output = args.classes_output.resolve()
    if args.mode == "prepare30":
        prepare30(args)
    else:
        if args.selection_file is None:
            parser.error("--mode build12 必须指定 --selection-file")
        args.selection_file = args.selection_file.resolve()
        build12(args)


if __name__ == "__main__":
    main()
