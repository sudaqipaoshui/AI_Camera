#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Long jump score extraction tool.
Features:
1) Extract score records with optional time filtering
2) Output ordered results to CSV
3) Optional per-person summary
"""

import argparse
import csv
import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path


def parse_timestamp(line: str):
    """Parse timestamp from a log line."""
    pattern = r"(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}\.\d{3})"
    match = re.search(pattern, line)
    if match:
        try:
            return datetime.strptime(match.group(1), "%Y-%m-%d %H:%M:%S.%f")
        except Exception:
            return None
    return None


def filter_by_time_range(lines, start_time=None, end_time=None):
    """Filter log lines by time range."""
    if not start_time and not end_time:
        return lines

    filtered = []
    skipped_before = 0
    skipped_after = 0
    included = 0

    for line in lines:
        timestamp = parse_timestamp(line)
        if timestamp:
            if start_time and timestamp < start_time:
                skipped_before += 1
                continue
            if end_time and timestamp > end_time:
                skipped_after += 1
                continue
            included += 1
        filtered.append(line)

    print("Time filter details:")
    if start_time:
        print(f"  Start time: {start_time}")
    if end_time:
        print(f"  End time: {end_time}")
    print(f"  Lines before filter: {len(lines)}")
    print(f"  Lines after filter: {len(filtered)}")
    print(f"  Included lines: {included}")
    print(f"  Skipped (before start): {skipped_before}")
    print(f"  Skipped (after end): {skipped_after}")

    return filtered


def parse_score_line(line: str):
    """Parse one score record from a log line."""
    # onSportDone ... recordId=... name=..., score=...
    match = re.search(
        r"onSportDone .*?(?:recordId=([^,]+).*?)? name=([^,]+), score=(\d+)",
        line,
    )
    if match:
        record_id = match.group(1)
        name = match.group(2).strip()
        score = int(match.group(3))
        return {
            "name": name,
            "score": score,
            "record_id": record_id,
            "source": "onSportDone",
            "timestamp": parse_timestamp(line),
            "raw_line": line.strip(),
        }

    # DsScoreTaskModule executeTask ... taskId=... name=..., score=...
    match = re.search(
        r"DsScoreTaskModule: executeTask .*?(?:taskId=([^,]+).*?)? name=([^,]+), score=(\d+)",
        line,
    )
    if match:
        record_id = match.group(1)
        name = match.group(2).strip()
        score = int(match.group(3))
        return {
            "name": name,
            "score": score,
            "record_id": record_id,
            "source": "executeTask",
            "timestamp": parse_timestamp(line),
            "raw_line": line.strip(),
        }

    # insertStep2 ... name=..., score=...
    match = re.search(r"insertStep2 .*?name=([^,]+).*?score=(\d+)", line)
    if match:
        name = match.group(1).strip()
        score = int(match.group(2))
        return {
            "name": name,
            "score": score,
            "record_id": None,
            "source": "insertStep2",
            "timestamp": parse_timestamp(line),
            "raw_line": line.strip(),
        }

    return None


def dedupe_records(records):
    """De-duplicate records from multiple sources while keeping order."""
    seen = set()
    deduped = []
    for rec in records:
        if rec.get("record_id"):
            key = ("id", rec["record_id"], rec["name"], rec["score"])
        elif rec.get("timestamp"):
            key = ("ts", rec["timestamp"], rec["name"], rec["score"])
        else:
            key = ("raw", rec["raw_line"])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(rec)
    return deduped


def parse_log_file(log_file_path, start_time=None, end_time=None, dedupe=True):
    """Parse a log file and return score records in appearance order."""
    with open(log_file_path, "r", encoding="utf-8", errors="ignore") as f:
        lines = f.readlines()

    if start_time or end_time:
        lines = filter_by_time_range(lines, start_time, end_time)

    records = []
    for line in lines:
        parsed = parse_score_line(line)
        if parsed:
            records.append(parsed)

    if dedupe:
        records = dedupe_records(records)

    return records


def generate_csv(records, output_csv):
    """Generate CSV from records."""
    output_csv = Path(output_csv)
    output_csv.parent.mkdir(parents=True, exist_ok=True)

    headers = ["index", "name", "score", "timestamp", "source"]
    rows = [headers]
    for idx, rec in enumerate(records, start=1):
        ts = rec["timestamp"].strftime("%Y-%m-%d %H:%M:%S.%f")[:-3] if rec.get("timestamp") else ""
        rows.append([idx, rec["name"], rec["score"], ts, rec["source"]])

    with open(output_csv, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerows(rows)

    print(f"CSV saved: {output_csv}")


def print_records(records):
    """Print records in order."""
    for idx, rec in enumerate(records, start=1):
        print(f"{idx}. {rec['name']} {rec['score']}")


def print_summary(records):
    """Print summary grouped by name."""
    grouped = defaultdict(list)
    for rec in records:
        grouped[rec["name"]].append(rec["score"])

    print("\nSummary by name:")
    for name, scores in grouped.items():
        avg = sum(scores) / len(scores)
        print(f"{name}: count={len(scores)}, min={min(scores)}, max={max(scores)}, avg={avg:.2f}")


def main():
    parser = argparse.ArgumentParser(description="Long jump score extraction tool")
    parser.add_argument("log_file", type=str, help="Log file path")
    parser.add_argument("--start-time", type=str, help="Start time (YYYY-MM-DD HH:MM:SS)")
    parser.add_argument("--end-time", type=str, help="End time (YYYY-MM-DD HH:MM:SS)")
    parser.add_argument(
        "--output-dir",
        type=str,
        default="Log/analysis",
        help="Output directory (default: Log/analysis)",
    )
    parser.add_argument(
        "--order",
        choices=["appearance", "name", "score"],
        default="appearance",
        help="Ordering for output (default: appearance)",
    )
    parser.add_argument("--summary", action="store_true", help="Print per-name summary")
    parser.add_argument(
        "--no-dedupe",
        action="store_true",
        help="Keep duplicates from multiple sources",
    )
    args = parser.parse_args()

    start_time = None
    end_time = None
    if args.start_time:
        start_time = datetime.strptime(args.start_time.strip(), "%Y-%m-%d %H:%M:%S")
    if args.end_time:
        end_time = datetime.strptime(args.end_time.strip(), "%Y-%m-%d %H:%M:%S")
    if start_time and end_time and start_time >= end_time:
        print("Invalid time range: start_time must be earlier than end_time.")
        return

    log_file = Path(args.log_file)
    if not log_file.exists():
        print(f"File not found: {log_file}")
        return

    records = parse_log_file(
        log_file,
        start_time=start_time,
        end_time=end_time,
        dedupe=not args.no_dedupe,
    )

    if not records:
        print("No score records found.")
        return

    if args.order == "name":
        records.sort(key=lambda r: (r["name"], r["timestamp"] or datetime.max))
    elif args.order == "score":
        records.sort(key=lambda r: r["score"], reverse=True)

    print_records(records)

    date_str = datetime.now().strftime("%Y%m%d")
    output_dir = Path(args.output_dir) / date_str
    output_csv = output_dir / f"{log_file.stem}_longjump_scores.csv"
    generate_csv(records, output_csv)

    if args.summary:
        print_summary(records)


if __name__ == "__main__":
    main()
