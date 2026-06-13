"""Parse a Grove GMK **imperial** product-guide main-boom chart and convert to metric.

For GMK models that publish only an imperial product guide (e.g. GMK7550). The imperial GMK chart
looks like:

    Main boom
    16,0 m - 60 m  120 000 kg  29 ft 2 in spread  360deg
    (53 ft - 197 ft) (264,500 lb) (100%)
    Pounds (thousands)
    Feet
    52.6 68.4 84.3 ... 196.9                       <- boom lengths (feet, decimal point)
    8   *1100.0                                     <- radius (ft) + capacities (1000s of lb)
    10  678.0 624.0
    ...

Capacities are in THOUSANDS OF POUNDS (678.0 = 678,000 lb); distances in feet. Output is metric
(radius/boom -> m via ft_to_m, capacity -> t via pounds_to_tonnes). Staggered columns are mapped by
x-position; the highest-capacity telescopic main-boom page is chosen (use --page to override).
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
from crane_tool.units import ft_to_m, pounds_to_tonnes  # noqa: E402

PIVOT_HEIGHT_M = 3.0
ASSUMED_MAX_ANGLE_DEG = 78.0
EXCLUDE = ("jib", "luffing", "extension", "bi-fold", "bifold", "swingaway", "runner", "erection")
NUMDOT = re.compile(r"^[*+]*\d+(\.\d+)?$")  # 678.0 / 52.6 / *1100.0 / 8


def num(tok: str) -> float | None:
    tok = tok.strip("*+ '’\"")
    return float(tok) if re.fullmatch(r"\d+(\.\d+)?", tok) else None


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


def _boom_header(lines):
    """Return (hdr_top, radius_x, boom_cols). 'Feet' marks the radius column; boom lengths follow
    on the same or next line."""
    for idx, (top, ws) in enumerate(lines):
        if ws and ws[0]["text"].lower() == "feet":
            radius_x = (ws[0]["x0"] + ws[0]["x1"]) / 2
            src = ws[1:]
            htop = top
            if sum(num(w["text"]) is not None for w in src) < 3 and idx + 1 < len(lines):
                htop, src = lines[idx + 1][0], lines[idx + 1][1]
            cols = [((w["x0"] + w["x1"]) / 2, num(w["text"])) for w in src if num(w["text"])]
            if len(cols) >= 3:
                return htop, radius_x, cols
    return None, None, None


def _max_cap_klb(lines) -> float:
    best = 0.0
    for _t, ws in lines:
        for w in ws:
            v = num(w["text"])
            if v is not None and 1 <= v <= 2000:
                best = max(best, v)
    return best


def _find_chart_page(pdf, want=None):
    if want is not None:
        return want, pdf.pages[want]
    cands = []
    for pi, page in enumerate(pdf.pages):
        text = (page.extract_text() or "").lower()
        if "main boom" in text and "pounds" in text and "feet" in text and "360" in text:
            if any(k in text for k in EXCLUDE):
                continue
            lines = _lines(page)
            if _boom_header(lines)[2] is not None:
                cands.append((pi, page, _max_cap_klb(lines)))
    if not cands:
        return None, None
    cands.sort(key=lambda c: c[2], reverse=True)
    return cands[0][0], cands[0][1]


def parse(pdf_path: Path, manufacturer: str, model: str, page_index=None) -> dict:
    with pdfplumber.open(str(pdf_path)) as pdf:
        pi, page = _find_chart_page(pdf, page_index)
        if page is None:
            raise SystemExit(f"No imperial main-boom chart found in {pdf_path.name}")
        lines = _lines(page)
        text = page.extract_text() or ""
        scale = 1000.0 if "thousand" in text.lower() else 1.0  # 'Pounds (thousands)'

        cw = re.search(r"\(([\d,]+)\s*lb\)", text)
        counterweight = (
            f"{cw.group(1)} lb counterweight, 100% / 360 deg (as charted)" if cw else "as charted"
        )

        hdr_top, radius_x, boom_cols = _boom_header(lines)
        if boom_cols is None:
            raise SystemExit("Could not locate boom-length column header ('Feet ...').")

        def nearest_boom(xc: float) -> float:
            return min(boom_cols, key=lambda c: abs(c[0] - xc))[1]

        grid: dict[float, dict[float, float]] = {}
        for top, ws in lines:
            if top <= hdr_top:
                continue
            first = ws[0]
            if abs((first["x0"] + first["x1"]) / 2 - radius_x) > 16:
                continue
            r_ft = num(first["text"])
            if r_ft is None or r_ft > 400:
                continue
            for w in ws[1:]:
                xc = (w["x0"] + w["x1"]) / 2
                if xc <= radius_x + 15:
                    continue
                v = num(w["text"])
                if v is None:
                    continue
                lbs = v * scale
                if lbs < 1000:
                    continue
                b = nearest_boom(xc)
                prev = grid.setdefault(b, {}).get(r_ft)
                grid[b][r_ft] = lbs if prev is None else max(prev, lbs)

        boom_configs = []
        for boom_ft in sorted(grid):
            pts = sorted(grid[boom_ft].items())
            cleaned, last = [], float("inf")
            for r, lb in pts:
                if lb <= last + 1e-6:
                    cleaned.append((r, lb))
                    last = lb
            if len(cleaned) < 2:
                continue
            boom_m = ft_to_m(boom_ft)
            tip = round(PIVOT_HEIGHT_M + boom_m * math.sin(math.radians(ASSUMED_MAX_ANGLE_DEG)), 1)
            boom_configs.append(
                {
                    "boom_length_m": round(boom_m, 1),
                    "max_tip_height_m": tip,
                    "points": [
                        {"radius_m": round(ft_to_m(r), 2), "capacity_t": round(pounds_to_tonnes(lb), 2)}
                        for r, lb in cleaned
                    ],
                }
            )

        max_cap = round(max(pounds_to_tonnes(c) for d in grid.values() for c in d.values()), 1)
        max_boom = round(ft_to_m(max(grid)), 1)

    return {
        "manufacturer": manufacturer,
        "model": model,
        "type": "All Terrain",
        "max_capacity_t": max_cap,
        "max_boom_m": max_boom,
        "counterweight": counterweight,
        "source_pdf": pdf_path.name,
        "notes": f"Main-boom chart, page {pi + 1}, converted from the IMPERIAL guide "
        "(thousands of lb -> t, ft -> m). Tip heights APPROXIMATE.",
        "data_status": "EXTRACTED from imperial source PDF via pdfplumber and converted to metric "
        "(upward-misread points dropped; tip heights approximate). Spot-check advised.",
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
