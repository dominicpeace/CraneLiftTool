"""Parse a Grove **metric** product-guide load chart (Manitowoc GMK all-terrain cranes).

Targets the metric telescopic-boom main chart, e.g.:

    Telescopic boom ...
    10,2 - 40,0 m   6,2 m   360°   7,5 t          <- boom range, outrigger, slew, counterweight
    m  10,2(0°) 10,2 14,0 ... 40,0  m              <- radius col header 'm' + boom lengths (metres)
    3,0  50,0* 44,5 44,5 41,5 37,5            3,0   <- radius (m) + capacities (tonnes) + mirror

Values use a decimal comma (50,0 = 50.0). Capacities are already in tonnes and distances in
metres, so no unit conversion is needed. The chart is staggered, so capacities are mapped to
boom-length columns by x-position. Among multiple chart pages, the telescopic-boom page with the
highest capacity is chosen (the max-counterweight configuration); use --page to override.

Usage:
    python ingest/parse_grove_metric.py data/pdfs/manitowoc/GMK3050-3-metric.pdf \
        --manufacturer Grove --model GMK3050-3 --out data/cranes/grove_gmk3050_3.json

Tip heights are APPROXIMATE (no boom-angle data in these charts). Always verify against the
source load chart before use.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from pathlib import Path

import pdfplumber

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

PIVOT_HEIGHT_M = 3.0          # approximate boom-pivot height for these large cranes
ASSUMED_MAX_ANGLE_DEG = 78.0  # no angle data in metric charts; assume a typical max for tip height
EXCLUDE = ("jib", "luffing", "extension", "bi-fold", "bifold", "swingaway", "runner", "erection")
METRIC = re.compile(r"^[*+]*\d+(,\d+)?$")  # 50,0 / 44,5 / 8 / *50,0


def metric_float(tok: str) -> float | None:
    """Parse a metric number token (decimal comma), stripping markers and any '(...)' suffix."""
    tok = re.sub(r"\(.*?\)", "", tok).strip("*+ ")
    if not re.fullmatch(r"\d+(,\d+)?", tok):
        return None
    return float(tok.replace(",", "."))


def _lines(page):
    rows: list[tuple[float, list]] = []
    for w in sorted(page.extract_words(), key=lambda w: (w["top"], w["x0"])):
        for i, (top, words) in enumerate(rows):
            if abs(w["top"] - top) <= 4:
                words.append(w)
                rows[i] = (top, words)
                break
        else:
            rows.append((w["top"], [w]))
    return [(top, sorted(ws, key=lambda w: w["x0"])) for top, ws in rows]


def _header_line(lines):
    """The boom-length column header: first token 'm' followed by >=3 metric numbers."""
    for top, ws in lines:
        if ws and ws[0]["text"].lower() == "m":
            nums = [w for w in ws[1:] if metric_float(w["text"]) is not None]
            if len(nums) >= 3:
                return top, ws
    return None, None


def _max_capacity(lines) -> float:
    best = 0.0
    _, hdr = _header_line(lines)
    for top, ws in lines:
        for w in ws:
            v = metric_float(w["text"])
            if v is not None and 0 < v < 1000:
                best = max(best, v)
    return best


def _find_chart_page(pdf, want_index=None):
    if want_index is not None:
        return want_index, pdf.pages[want_index]
    cands = []
    for pi, page in enumerate(pdf.pages):
        text = (page.extract_text() or "").lower()
        if "telescopic boom" in text and "360" in text:
            if any(k in text for k in EXCLUDE):
                continue
            lines = _lines(page)
            if _header_line(lines)[1] is not None:
                cands.append((pi, page, _max_capacity(lines)))
    if not cands:
        return None, None
    cands.sort(key=lambda c: c[2], reverse=True)
    return cands[0][0], cands[0][1]


def parse(pdf_path: Path, manufacturer: str, model: str, page_index=None) -> dict:
    with pdfplumber.open(str(pdf_path)) as pdf:
        pi, page = _find_chart_page(pdf, page_index)
        if page is None:
            raise SystemExit(f"No metric telescopic-boom chart found in {pdf_path.name}")
        lines = _lines(page)
        full_text = page.extract_text() or ""

        cw = re.search(r"360°?\s*([\d,]+)\s*t\b", full_text)
        counterweight = (
            f"{cw.group(1)} t counterweight, 360 deg (as charted)" if cw else "as charted"
        )

        hdr_top, hdr_ws = _header_line(lines)
        if hdr_ws is None:
            raise SystemExit("Could not locate the 'm <boom lengths>' header line.")
        radius_x = (hdr_ws[0]["x0"] + hdr_ws[0]["x1"]) / 2
        right_m_x = (hdr_ws[-1]["x0"] + hdr_ws[-1]["x1"]) / 2  # mirrored radius column on the right
        boom_cols = []  # (x_center, boom_m)
        for w in hdr_ws[1:-1]:
            bv = metric_float(w["text"])
            if bv is not None:
                boom_cols.append(((w["x0"] + w["x1"]) / 2, bv))
        if not boom_cols:
            raise SystemExit("No boom-length columns parsed from header.")

        def nearest_boom(xc: float) -> float:
            return min(boom_cols, key=lambda c: abs(c[0] - xc))[1]

        # grid[boom_m][radius_m] = capacity_t (keep the max where columns merge, e.g. the (0deg) col)
        grid: dict[float, dict[float, float]] = {}
        for top, ws in lines:
            if top <= hdr_top:
                continue
            first = ws[0]
            if abs((first["x0"] + first["x1"]) / 2 - radius_x) > 16:
                continue
            r = metric_float(first["text"])
            if r is None or r > 200:
                continue
            for w in ws[1:]:
                xc = (w["x0"] + w["x1"]) / 2
                if xc <= radius_x + 15 or xc >= right_m_x - 15:
                    continue  # skip the mirrored radius / out-of-grid tokens
                cap = metric_float(w["text"])
                if cap is None or cap <= 0:
                    continue
                b = nearest_boom(xc)
                prev = grid.setdefault(b, {}).get(r)
                grid[b][r] = cap if prev is None else max(prev, cap)

        boom_configs = []
        for boom_m in sorted(grid):
            pts = sorted(grid[boom_m].items())
            cleaned, last = [], float("inf")
            for r, cap in pts:
                if cap <= last + 1e-6:
                    cleaned.append((r, cap))
                    last = cap
            if len(cleaned) < 2:
                continue
            tip = round(PIVOT_HEIGHT_M + boom_m * math.sin(math.radians(ASSUMED_MAX_ANGLE_DEG)), 1)
            boom_configs.append(
                {
                    "boom_length_m": round(boom_m, 1),
                    "max_tip_height_m": tip,
                    "points": [{"radius_m": r, "capacity_t": cap} for r, cap in cleaned],
                }
            )

        max_cap = round(max(c for d in grid.values() for c in d.values()), 1)
        max_boom = round(max(grid), 1)

    return {
        "manufacturer": manufacturer,
        "model": model,
        "type": "All Terrain",
        "max_capacity_t": max_cap,
        "max_boom_m": max_boom,
        "counterweight": counterweight,
        "source_pdf": pdf_path.name,
        "notes": f"Metric telescopic-boom chart, page {pi + 1}. Tip heights APPROXIMATE "
        "(no boom-angle data in metric charts).",
        "data_status": "EXTRACTED from metric source PDF via pdfplumber (capacities in tonnes "
        "from chart; upward-misread points dropped; tip heights approximate). Spot-check advised.",
        "boom_configs": boom_configs,
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("pdf", type=Path)
    ap.add_argument("--manufacturer", required=True)
    ap.add_argument("--model", required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--page", type=int, default=None)
    args = ap.parse_args(argv)

    data = parse(args.pdf, args.manufacturer, args.model, page_index=args.page)
    args.out.write_text(json.dumps(data, indent=2), encoding="utf-8")
    n = sum(len(b["points"]) for b in data["boom_configs"])
    print(
        f"Wrote {args.out} : {len(data['boom_configs'])} boom configs, {n} points, "
        f"max cap {data['max_capacity_t']} t, max boom {data['max_boom_m']} m."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
