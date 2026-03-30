#!/usr/bin/env python3
# Collect stock CSV files referenced in big_movers_result.csv
# into a single output folder.
#
# Usage:
#   python collect_stocks.py
#   python collect_stocks.py --result big_movers_result.csv --out collected_stocks

import argparse
import csv
import os
import shutil
import sys


# ── Config ──────────────────────────────────────────────
SCRIPT_DIR     = os.path.dirname(os.path.abspath(__file__))
DEFAULT_RESULT = os.path.join(SCRIPT_DIR, "big_movers_result.csv")
DEFAULT_OUT    = os.path.join(SCRIPT_DIR, "collected_stocks")

SOURCE_DIRS = [
    r"D:\US_stocks_daily_data\delisted stocks from 2000",
    r"D:\US_stocks_daily_data\listed stocks from 2000",
]
# ────────────────────────────────────────────────────────


def find_csv(symbol, source_dirs):
    for d in source_dirs:
        for fname in [f"{symbol}.csv", f"{symbol.lower()}.csv"]:
            path = os.path.join(d, fname)
            if os.path.exists(path):
                return path
    return None


def main():
    parser = argparse.ArgumentParser(description="Collect stock CSVs from big_movers_result.csv")
    parser.add_argument("--result", default=DEFAULT_RESULT, help="Path to big_movers_result.csv")
    parser.add_argument("--out",    default=DEFAULT_OUT,    help="Output folder")
    args = parser.parse_args()

    if not os.path.exists(args.result):
        print(f"[ERROR] Result file not found: {args.result}")
        sys.exit(1)

    # Read unique symbols
    symbols = set()
    with open(args.result, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            sym = (row.get("symbol") or "").strip().upper()
            if sym:
                symbols.add(sym)

    print(f"Found {len(symbols)} unique symbols in {os.path.basename(args.result)}")

    # Create output folder
    os.makedirs(args.out, exist_ok=True)

    found   = 0
    missing = []

    for sym in sorted(symbols):
        src = find_csv(sym, SOURCE_DIRS)
        if src:
            dst = os.path.join(args.out, f"{sym}.csv")
            shutil.copy2(src, dst)
            found += 1
            print(f"  [OK] {sym}  <-  {os.path.basename(os.path.dirname(src))}")
        else:
            missing.append(sym)
            print(f"  [--] {sym}  not found")

    print(f"\nDone. Copied {found}/{len(symbols)} files to:")
    print(f"  {args.out}")

    if missing:
        print(f"\nMissing ({len(missing)}):")
        for s in missing:
            print(f"  {s}")
        missing_path = os.path.join(args.out, "_missing.txt")
        with open(missing_path, "w", encoding="utf-8") as f:
            f.write("\n".join(missing) + "\n")
        print(f"\nMissing list saved to: {missing_path}")


if __name__ == "__main__":
    main()
