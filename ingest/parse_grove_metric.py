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


def _cx(w) -> float:
    return (w["x0"] + w["x1"]) / 2


def boom_col_val(tok: str) -> float | None:
    """Boom length from a header token; takes the first number, tolerating ranges like
    '18,6-19,0' (telescope range) and parenthetical/marker suffixes."""
    tok = re.sub(r"\(.*?\)", "", tok).strip("*+ ")
    m = re.match(r"\d+(,\d+)?", tok)
    return float(m.group(0).replace(",", ".")) if m else None


def _header_line(lines):
    """The boom-length column header: first token 'm' followed by >=3 boom-length numbers."""
    for top, ws in lines:
        if ws and ws[0]["text"].lower() == "m":
            if sum(boom_col_val(w["text"]) is not None for w in ws[1:]) >= 3:
                return top, ws
    return None, None


def _extract_grid(lines):
    """Parse the chart grid on a page. Returns (grid, boom_cols, radius_x, hdr_top) or all-None."""
    hdr_top, hdr_ws = _header_line(lines)
    if hdr_ws is None:
        return None, None, None, None
    radius_x = _cx(hdr_ws[0])
    right_m_x = _cx(hdr_ws[-1])  # mirrored radius column on the right
    boom_cols = [(_cx(w), boom_col_val(w["text"])) for w in hdr_ws[1:-1]
                 if boom_col_val(w["text"]) is not None]
    if not boom_cols:
        return None, None, None, None

    def nearest_boom(xc: float) -> float:
        return min(boom_cols, key=lambda c: abs(c[0] - xc))[1]

    grid: dict[float, dict[float, float]] = {}
    for top, ws in lines:
        if top <= hdr_top:
            continue
        if abs(_cx(ws[0]) - radius_x) > 16:
            continue
        r = metric_float(ws[0]["text"])
        if r is None or r > 200:
            continue
        for w in ws[1:]:
            xc = _cx(w)
            if xc <= radius_x + 15 or xc >= right_m_x - 15:
                continue  # skip the mirrored radius / out-of-grid tokens
            if "," not in w["text"]:
                continue  # real capacities always carry a comma (kg-thousands or t-decimal);
                #            bare integers are footnote refs / dimensions, not capacities
            cap = metric_float(w["text"])
            if cap is None or cap <= 0:
                continue
            b = nearest_boom(xc)
            prev = grid.setdefault(b, {}).get(r)
            grid[b][r] = cap if prev is None else max(prev, cap)
    return grid, boom_cols, radius_x, hdr_top


def _grid_max(grid) -> float:
    return max((c for d in grid.values() for c in d.values()), default=0.0)


def _find_chart_page(pdf, want_index=None):
    """Pick the main telescopic-boom chart: among 'telescopic boom' + 360 pages with a valid grid,
    the one whose parsed grid has the highest capacity (the full-counterweight main chart). Ranking
    on the parsed grid (not raw page numbers) ignores stray spec/dimension figures."""
    if want_index is not None:
        return want_index, pdf.pages[want_index]
    best = None  # (pi, page, grid_max)
    for pi, page in enumerate(pdf.pages):
        text = (page.extract_text() or "").lower()
        if "telescopic boom" in text and "360" in text:
            grid, *_ = _extract_grid(_lines(page))
            if grid:
                gm = _grid_max(grid)
                if best is None or gm > best[2] + 1e-6:
                    best = (pi, page, gm)
    return (best[0], best[1]) if best else (None, None)


def parse(pdf_path: Path, manufacturer: str, model: str, page_index=None) -> dict:
    with pdfplumber.open(str(pdf_path)) as pdf:
        pi, page = _find_chart_page(pdf, page_index)
        if page is None:
            raise SystemExit(f"No metric telescopic-boom chart found in {pdf_path.name}")
        lines = _lines(page)
        full_text = page.extract_text() or ""

        cw = re.search(r"360°?\s*([\d., ]+?)\s*(kg|t)\b", full_text)
        counterweight = (
            f"{cw.group(1).strip()} {cw.group(2)} counterweight, 360 deg (as charted)"
            if cw else "as charted"
        )

        grid, boom_cols, radius_x, hdr_top = _extract_grid(lines)
        if not grid:
            raise SystemExit("Could not parse a chart grid on the selected page.")

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

        max_cap = round(_grid_max(grid), 1)
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
