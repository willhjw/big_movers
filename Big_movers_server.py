#!/usr/bin/env python3
# Big Movers Viewer Server
# Usage: python Big_movers_server.py
# Then open http://localhost:5051/ in browser

import csv
import os
import json
from flask import Flask, jsonify, send_from_directory, request, Response

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__, static_folder=SCRIPT_DIR, static_url_path="")

# 配置路径
RESULTS_CSV = os.path.join(SCRIPT_DIR, "big_movers_result.csv")
STOCKS_DIRS = [
    os.path.join(SCRIPT_DIR, "collected_stocks"),
]

# SPY benchmark data source (UI "VS" overlay)
SPY_HIST_CSV = os.path.join(SCRIPT_DIR, "SPY Historical Data.csv")
_SPY_BARS_CACHE = None

def _normalize_date_maybe(raw):
    s = str(raw or "").strip()
    if not s:
        return ""
    # Already ISO-like
    if len(s) >= 10 and s[4] == "-" and s[7] == "-":
        return s[:10]
    # MM/DD/YYYY -> YYYY-MM-DD
    if len(s) >= 10 and s[2] == "/" and s[5] == "/":
        mm = s[0:2]
        dd = s[3:5]
        yyyy = s[6:10]
        if mm.isdigit() and dd.isdigit() and yyyy.isdigit():
            return f"{yyyy}-{mm}-{dd}"
    return s

def _parse_float_maybe(x):
    try:
        if x is None:
            return None
        s = str(x).strip()
        if not s:
            return None
        # tolerate thousands separators
        s = s.replace(",", "")
        v = float(s)
        return v
    except (ValueError, TypeError):
        return None

def _parse_volume_maybe(x):
    """
    Parse volume like:
    - 52.00M
    - 1.23B
    - 450K
    - plain numeric
    """
    try:
        if x is None:
            return 0.0
        s = str(x).strip()
        if not s:
            return 0.0
        s = s.replace(",", "")
        if s.lower() == "nan":
            return 0.0

        mult = 1.0
        last = s[-1].upper()
        if last == "M":
            mult = 1e6
            s = s[:-1]
        elif last == "B":
            mult = 1e9
            s = s[:-1]
        elif last == "K":
            mult = 1e3
            s = s[:-1]

        v = float(s)
        return v * mult
    except (ValueError, TypeError):
        return 0.0

def _load_spy_bars():
    global _SPY_BARS_CACHE
    if _SPY_BARS_CACHE is not None:
        return _SPY_BARS_CACHE

    if not os.path.exists(SPY_HIST_CSV):
        _SPY_BARS_CACHE = []
        return _SPY_BARS_CACHE

    bars = []
    try:
        with open(SPY_HIST_CSV, "r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Support both:
                # - Date, Price, Open, High, Low, Vol.
                # - DateTime, Open, High, Low, Close, Volume
                raw_date = row.get("Date") or row.get("DateTime")
                date_str = _normalize_date_maybe(raw_date)
                if not date_str:
                    continue
                o = _parse_float_maybe(row.get("Open"))
                h = _parse_float_maybe(row.get("High"))
                l = _parse_float_maybe(row.get("Low"))
                c = _parse_float_maybe(row.get("Close"))
                if c is None:
                    c = _parse_float_maybe(row.get("Price"))
                v = _parse_volume_maybe(row.get("Volume"))
                if not v:
                    v = _parse_volume_maybe(row.get("Vol."))
                if c is None or c <= 0:
                    continue
                if o is None or h is None or l is None:
                    continue
                bars.append({
                    "time": date_str,
                    "open": o,
                    "high": h,
                    "low": l,
                    "close": c,
                    "volume": v,
                })
    except Exception:
        bars = []

    bars.sort(key=lambda x: x.get("time") or "")
    _SPY_BARS_CACHE = bars
    return _SPY_BARS_CACHE


def _resolve_index_html_path():
    # Repo uses Big_movers.html; tolerate lowercase for clones on case-sensitive FS
    for name in ("Big_movers.html", "big_movers.html"):
        p = os.path.join(SCRIPT_DIR, name)
        if os.path.exists(p):
            return p
    return None


@app.route("/")
def index():
    html_path = _resolve_index_html_path()
    if not html_path:
        return f"Big_movers.html not found in {SCRIPT_DIR}", 404
    with open(html_path, "r", encoding="utf-8") as f:
        content = f.read()
    return Response(content, mimetype="text/html")


@app.route("/api/results")
def api_results():
    if not os.path.exists(RESULTS_CSV):
        return jsonify({"error": "big_movers_result.csv not found"}), 404
    rows = []
    with open(RESULTS_CSV, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
    return jsonify(rows)


@app.route("/api/ohlcv")
def api_ohlcv():
    symbol = (request.args.get("symbol") or "").strip().upper()
    if not symbol:
        return jsonify({"error": "symbol required"}), 400

    # Special-case SPY: serve from SPY Historical Data.csv
    if symbol == "SPY":
        try:
            return jsonify(_load_spy_bars())
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    # 在所有目录里查找
    path = None
    for d in STOCKS_DIRS:
        for fname in [f"{symbol}.csv", f"{symbol.lower()}.csv"]:
            c = os.path.join(d, fname)
            if os.path.exists(c):
                path = c
                break
        if path:
            break

    if not path:
        return jsonify({"error": f"{symbol}.csv not found in any configured directory"}), 404

    bars = []
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            reader = csv.reader(f)
            header = next(reader, None)
            if not header:
                return jsonify([])
            # 判断格式
            if len(header) >= 2 and "date" in (header[1] or "").lower():
                fmt = "new"
            elif len(header) >= 1 and "date" in (header[0] or "").lower():
                fmt = "noindex"
            else:
                fmt = "old"
            for row in reader:
                try:
                    if fmt == "new":
                        # [idx, date, open, high, low, close, volume]
                        if len(row) < 7:
                            continue
                        t = row[1].strip()
                        o = float(row[2])
                        h = float(row[3])
                        l = float(row[4])
                        c = float(row[5])
                        v = float(row[6])
                    elif fmt == "noindex":
                        # [DateTime, Open, High, Low, Close, Volume]
                        if len(row) < 6:
                            continue
                        raw_t = row[0].strip()
                        if len(raw_t) == 10 and raw_t[2] == '/':
                            parts = raw_t.split('/')
                            t = f"{parts[2]}-{parts[0]:>02}-{parts[1]:>02}"
                        else:
                            t = raw_t
                        o = float(row[1])
                        h = float(row[2])
                        l = float(row[3])
                        c = float(row[4])
                        v = float(row[5])
                    else:
                        # [date, close, open, high, low, volume, ...]
                        if len(row) < 6:
                            continue
                        t = row[0].strip()
                        c = float(row[1])
                        o = float(row[2])
                        h = float(row[3])
                        l = float(row[4])
                        v = float(row[5])
                    if c <= 0:
                        continue
                    bars.append({"time": t, "open": o, "high": h, "low": l, "close": c, "volume": v})
                except (ValueError, IndexError):
                    continue
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    bars.sort(key=lambda x: x["time"])
    return jsonify(bars)


DRAWINGS_FILE = os.path.join(SCRIPT_DIR, "drawings.json")


@app.route("/api/drawings", methods=["GET", "POST"])
def api_drawings():
    if request.method == "GET":
        if not os.path.exists(DRAWINGS_FILE):
            return jsonify({})
        try:
            with open(DRAWINGS_FILE, "r", encoding="utf-8") as f:
                return jsonify(json.load(f))
        except Exception:
            return jsonify({})
    else:
        try:
            data = request.get_json(silent=True) or {}
            with open(DRAWINGS_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            return jsonify({"ok": True})
        except Exception as e:
            return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    print("Big Movers Viewer: http://localhost:5051/")
    app.run(host="127.0.0.1", port=5051, debug=False)