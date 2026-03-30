#!/usr/bin/env python3
# Check which ticker CSVs are missing a target date row.
#
# Usage:
#   python check_missing_date_tickers.py
#   python check_missing_date_tickers.py --date 2025-09-12
#   python check_missing_date_tickers.py --dir collected_stocks --out missing_2025-09-12.txt

import argparse
import csv
import os
import sys
from datetime import datetime


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_DIR = os.path.join(SCRIPT_DIR, "collected_stocks")
DEFAULT_DATE = "2025-09-12"


def normalize_date(s: str) -> str:
    """Normalize date string to YYYY-MM-DD if possible."""
    raw = (s or "").strip()
    if not raw:
        return ""

    # Already ISO-like.
    if len(raw) >= 10 and raw[4] == "-" and raw[7] == "-":
        return raw[:10]

    # MM/DD/YYYY
    if len(raw) >= 10 and raw[2] == "/" and raw[5] == "/":
        mm = raw[0:2]
        dd = raw[3:5]
        yyyy = raw[6:10]
        if mm.isdigit() and dd.isdigit() and yyyy.isdigit():
            return f"{yyyy}-{mm}-{dd}"

    # Try generic parser for robustness.
    for fmt in ("%Y/%m/%d", "%m/%d/%Y", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(raw, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue

    return raw


def detect_date_column(header):
    for col in ("DateTime", "Date", "date", "datetime"):
        if col in header:
            return col
    return None


def file_has_target_date(path: str, target_date: str) -> bool:
    try:
        with open(path, "r", encoding="utf-8", errors="replace", newline="") as f:
            reader = csv.DictReader(f)
            if not reader.fieldnames:
                return False
            date_col = detect_date_column(reader.fieldnames)
            if not date_col:
                return False
            for row in reader:
                dt = normalize_date(row.get(date_col, ""))
                if dt == target_date:
                    return True
        return False
    except Exception:
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Find ticker CSV files that are missing a specific date row."
    )
    parser.add_argument(
        "--date",
        default=DEFAULT_DATE,
        help="Target date in YYYY-MM-DD format (default: 2025-09-12)",
    )
    parser.add_argument(
        "--dir",
        dest="stocks_dir",
        default=DEFAULT_DIR,
        help="Directory containing ticker CSV files",
    )
    parser.add_argument(
        "--out",
        default=None,
        help="Optional output file path for missing ticker list",
    )
    args = parser.parse_args()

    target_date = normalize_date(args.date)
    if not target_date or len(target_date) != 10:
        print(f"[ERROR] Invalid date: {args.date}")
        sys.exit(1)

    stocks_dir = args.stocks_dir
    if not os.path.isabs(stocks_dir):
        stocks_dir = os.path.join(SCRIPT_DIR, stocks_dir)

    if not os.path.isdir(stocks_dir):
        print(f"[ERROR] Directory not found: {stocks_dir}")
        sys.exit(1)

    csv_files = sorted(
        f for f in os.listdir(stocks_dir) if f.lower().endswith(".csv")
    )
    if not csv_files:
        print(f"[WARN] No CSV files found in: {stocks_dir}")
        sys.exit(0)

    missing = []
    checked = 0
    for fname in csv_files:
        ticker = os.path.splitext(fname)[0].upper()
        path = os.path.join(stocks_dir, fname)
        checked += 1
        if not file_has_target_date(path, target_date):
            missing.append(ticker)

    print(f"Checked files: {checked}")
    print(f"Target date : {target_date}")
    print(f"Missing     : {len(missing)}")

    if missing:
        print("\nTickers missing target date:")
        for t in missing:
            print(t)

    out_path = args.out
    if out_path:
        if not os.path.isabs(out_path):
            out_path = os.path.join(SCRIPT_DIR, out_path)
    else:
        out_path = os.path.join(stocks_dir, f"_missing_{target_date}.txt")

    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(missing))
        if missing:
            f.write("\n")
    print(f"\nSaved missing list to: {out_path}")


if __name__ == "__main__":
    main()
