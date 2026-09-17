#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
跳远日志分析脚本
从 APP 日志中解析立定跳远成绩，输出 testid、name、成绩（cm）。
日志格式示例：
  SportFragmentViewModel: onSportDataChange updated, ... testerId=1998917228, name=离谱, ... status=FINISH, score=186
"""

import re
import csv
import argparse
from datetime import datetime
from pathlib import Path
from typing import List, Tuple, Optional


def parse_timestamp(line: str) -> Optional[datetime]:
    """解析日志行首时间戳，格式: 2026-02-04 13:49:17.593"""
    m = re.match(r"(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}\.\d{3})", line.strip())
    if m:
        try:
            return datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S.%f")
        except ValueError:
            return None
    return None


# 匹配: onSportDataChange updated, ... testerId=数字, name=xxx, ... status=FINISH, score=数字
FINISH_PATTERN = re.compile(
    r"onSportDataChange\s+updated\s*,.*?testerId=(\d+)\s*,\s*name=([^,]+)\s*,\s*.*?status=FINISH\s*,\s*score=(\d+)",
    re.DOTALL,
)


def parse_longjump_results(
    log_path: str,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
) -> List[Tuple[str, str, int, Optional[datetime]]]:
    """
    解析跳远日志，返回 (testid, name, 成绩_cm, timestamp) 列表。
    只保留 status=FINISH 的条目（一次有效跳远一条）。
    """
    results = []
    with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            ts = parse_timestamp(line)
            if start_time and ts and ts < start_time:
                continue
            if end_time and ts and ts > end_time:
                continue
            match = FINISH_PATTERN.search(line)
            if not match:
                continue
            tester_id, name, score_str = match.group(1), match.group(2).strip(), match.group(3)
            results.append((tester_id, name, int(score_str), ts))
    return results


def main():
    parser = argparse.ArgumentParser(description="跳远日志分析：输出 testid、name、成绩（cm）")
    parser.add_argument("log_file", type=str, help="APP 日志文件路径")
    parser.add_argument(
        "--start-time",
        type=str,
        default=None,
        metavar="YYYY-MM-DD HH:MM:SS",
        help="只分析该时间之后的记录",
    )
    parser.add_argument(
        "--end-time",
        type=str,
        default=None,
        metavar="YYYY-MM-DD HH:MM:SS",
        help="只分析该时间之前的记录",
    )
    parser.add_argument("--csv", type=str, default=None, help="结果输出到 CSV 文件")
    parser.add_argument("--no-header", action="store_true", help="CSV 不输出表头")
    args = parser.parse_args()

    log_path = Path(args.log_file)
    if not log_path.exists():
        print(f"❌ 日志文件不存在: {log_path}")
        return 1

    start_time = None
    end_time = None
    if args.start_time:
        try:
            start_time = datetime.strptime(args.start_time, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            print(f"❌ 无效的 --start-time: {args.start_time}")
            return 1
    if args.end_time:
        try:
            end_time = datetime.strptime(args.end_time, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            print(f"❌ 无效的 --end-time: {args.end_time}")
            return 1

    results = parse_longjump_results(str(log_path), start_time, end_time)

    if not results:
        print("未解析到任何跳远成绩（status=FINISH）。")
        if args.csv:
            with open(args.csv, "w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                if not args.no_header:
                    w.writerow(["testid", "name", "成绩(cm)"])
        return 0

    # 控制台表格
    print("=" * 60)
    print("跳远日志分析结果（testid, name, 成绩）")
    print("=" * 60)
    print(f"{'testid':<16} {'name':<12} {'成绩(cm)':<10}")
    print("-" * 60)
    for testid, name, score, _ in results:
        print(f"{testid:<16} {name:<12} {score:<10}")
    print("-" * 60)
    print(f"共 {len(results)} 条成绩")

    if args.csv:
        csv_path = Path(args.csv)
        csv_path.parent.mkdir(parents=True, exist_ok=True)
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            if not args.no_header:
                w.writerow(["testid", "name", "成绩(cm)"])
            for testid, name, score, _ in results:
                w.writerow([testid, name, score])
        print(f"✅ 已写入 CSV: {csv_path}")

    return 0


if __name__ == "__main__":
    exit(main())
