#!/usr/bin/env python3
"""记录一次类别级的 30 框人工审核结论，保留逐行状态和审核备注。"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audit-file", type=Path, required=True)
    parser.add_argument("--source-name", required=True)
    parser.add_argument("--status", choices=("pass", "fail"), required=True)
    parser.add_argument("--note", required=True)
    parser.add_argument("--force", action="store_true", help="允许覆盖已有非 pending 审核结论")
    args = parser.parse_args()
    with args.audit_file.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = reader.fieldnames
        rows = list(reader)
    if not fieldnames:
        raise ValueError("审核 CSV 缺少表头")
    matched = [row for row in rows if row["source_name"] == args.source_name]
    if len(matched) != 30:
        raise ValueError(f"{args.source_name} 应有 30 行审核样本，实际 {len(matched)}")
    if not args.force and any(row["review_status"].strip().lower() != "pending" for row in matched):
        raise ValueError(f"{args.source_name} 已有审核结论；如确认覆盖请传 --force")
    for row in matched:
        row["review_status"] = args.status
        row["review_note"] = args.note
    with args.audit_file.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"{args.source_name}: 已记录 {len(matched)} 个 {args.status}")


if __name__ == "__main__":
    main()
