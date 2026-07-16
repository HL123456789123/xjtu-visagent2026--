#!/usr/bin/env python3
"""把 ``audit_review.csv`` 中的标注样本渲染成每类一张可人工复核的联系表。"""

from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


TILE_WIDTH = 224
TILE_HEIGHT = 188
COLUMNS = 5


def parse_bbox(value: str) -> tuple[float, float, float, float]:
    _, x, y, width, height = value.split()
    return float(x), float(y), float(width), float(height)


def make_tile(row: dict[str, str]) -> Image.Image:
    with Image.open(row["image_path"]) as opened:
        image = opened.convert("RGB")
    image.thumbnail((TILE_WIDTH, TILE_HEIGHT - 28), Image.Resampling.LANCZOS)
    tile = Image.new("RGB", (TILE_WIDTH, TILE_HEIGHT), "white")
    offset_x = (TILE_WIDTH - image.width) // 2
    offset_y = 24 + (TILE_HEIGHT - 28 - image.height) // 2
    tile.paste(image, (offset_x, offset_y))
    x, y, width, height = parse_bbox(row["bbox_yolo"])
    left = offset_x + (x - width / 2) * image.width
    top = offset_y + (y - height / 2) * image.height
    right = offset_x + (x + width / 2) * image.width
    bottom = offset_y + (y + height / 2) * image.height
    draw = ImageDraw.Draw(tile)
    draw.rectangle((left, top, right, bottom), outline="#ef4444", width=3)
    draw.text((5, 5), f"#{row['review_index']}  {row['source_group']}", fill="black")
    return tile


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audit-file", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()
    rows_by_class: dict[str, list[dict[str, str]]] = defaultdict(list)
    with args.audit_file.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            rows_by_class[row["source_name"]].append(row)
    args.output_root.mkdir(parents=True, exist_ok=True)
    for source_name, rows in sorted(rows_by_class.items()):
        rows.sort(key=lambda row: int(row["review_index"]))
        sheet_rows = (len(rows) + COLUMNS - 1) // COLUMNS
        sheet = Image.new("RGB", (COLUMNS * TILE_WIDTH, sheet_rows * TILE_HEIGHT), "#e5e7eb")
        for index, row in enumerate(rows):
            sheet.paste(make_tile(row), ((index % COLUMNS) * TILE_WIDTH, (index // COLUMNS) * TILE_HEIGHT))
        sheet.save(args.output_root / f"{source_name}.jpg", quality=92)
    print(f"已生成 {len(rows_by_class)} 张审核联系表: {args.output_root}")


if __name__ == "__main__":
    main()
