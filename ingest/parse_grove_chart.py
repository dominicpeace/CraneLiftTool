"""Parse a Grove imperial main-boom load chart from a (text-based) PDF into a crane JSON.

Targets the standard Grove rough-terrain chart layout:
  - a header line like '40 - 125 ft.  11,500 lbs.  100%  360' (boom range, counterweight, %, deg)
  - a 'Feet  40 45 55 ... 125' boom-length column header
  - radius rows (feet) with capacity cells (pounds), each followed by a boom-angle row in parens

Maps each capacity cell to its boom-length column by x-coordinate (the chart is staggered, so
left-alignment is wrong). Capacities convert lb->t, distances ft->m. Max tip height per boom is
APPROXIMATED from the highest charted boom angle and must be treated as indicative.

Usage:
    python ingest/parse_grove_chart.py data/pdfs/Grove-RT870.pdf \
        --manufacturer Grove --model RT870 --out data/cranes/grove_rt870.json

Always review the output against the source PDF before use.
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

PIVOT_HEIGHT_M = 2.4  # approximate boom-foot pin height above ground for tip-height estimate
NUM = re.compile(r"^\*?[\d,]+$")
HEADER_RE = re.compile(r"(\d+)\s*-\s*(\d+)\s*ft\.?\s+([\d,]+)\s*lbs", re.IGNORECASE)


def _lines(page):
    """Group a page's words into visual rows keyed by their 'top', tolerance ~4px."""
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


def _find_chart_page(pdf):
    """Pick the primary chart page: header with '100%' and a 'Feet <booms>' column row."""
    for pi, page in enumerate(pdf.pages):
        text = page.extract_text() or ""
        if "Pounds" in text and re.search(r"Feet\s+\d+", text) and "100%" in text:
            return pi, page
    return None, None


def _to_float(tok: str) -> float:
    return float(tok.replace(",", "").replace("*", ""))


def parse(pdf_path: Path, manufacturer: str, model: str) -> dict:
    with pdfplumber.open(str(pdf_path)) as pdf:
        pi, page = _find_chart_page(pdf)
        if page is None:
            raise SystemExit(f"No standard Grove chart page found in {pdf_path.name}")
        lines = _lines(page)
        full_text = page.extract_text() or ""

        # Header: boom range + counterweight.
        m = HEADER_RE.search(full_text)
        counterweight = (
            f"{m.group(3)} lb counterweight, 100% / 360 deg (as charted)" if m else "as charted"
        )

        # Boom-length column header: the line beginning with 'Feet'.
        boom_cols: list[tuple[float, float]] = []  # (x_center, boom_ft)
        hdr_top = None
        for top, ws in lines:
            if ws and ws[0]["text"].lower() == "feet":
                hdr_top = top
                for w in ws[1:]:
                    if w["text"].isdigit():
                        boom_cols.append(((w["x0"] + w["x1"]) / 2, float(w["text"])))
                break
        if not boom_cols or hdr_top is None:
            raise SystemExit("Could not locate boom-length column header ('Feet ...').")

        # End of the main grid: the 'Minimum boom angle ...' footer (a secondary 0-deg chart and
        # the page header lie outside this band and must be ignored).
        end_top = float("inf")
        for top, ws in lines:
            if top > hdr_top and " ".join(w["text"] for w in ws).lower().startswith(
                "minimum boom angle"
            ):
                end_top = top
                break

        def in_grid(top: float) -> bool:
            return hdr_top < top < end_top

        def nearest_boom(xc: float) -> float:
            return min(boom_cols, key=lambda c: abs(c[0] - xc))[1]

        # Collect radius labels, capacity cells, angle cells with positions.
        radius_labels: list[tuple[float, float]] = []  # (top, radius_ft)
        caps: list[tuple[float, float, float]] = []     # (top, x_center, lbs)
        angles: list[tuple[float, float, float]] = []    # (top, x_center, deg)
        for top, ws in lines:
            if not in_grid(top):
                continue
            for w in ws:
                t = w["text"]
                xc = (w["x0"] + w["x1"]) / 2
                if 65 <= w["x0"] <= 75 and t.isdigit() and int(t) <= 400:
                    radius_labels.append((top, float(t)))
                elif t.startswith("(") and t.rstrip(")").lstrip("(").replace(".", "").isdigit():
                    angles.append((top, xc, float(t.strip("()"))))
                elif NUM.match(t) and "," in t:
                    caps.append((top, xc, _to_float(t)))

        def nearest_radius(top: float) -> float | None:
            cand = [(abs(top - rt), r) for rt, r in radius_labels]
            if not cand:
                return None
            d, r = min(cand)
            return r if d <= 8 else None

        # boom_ft -> {radius_ft: lbs} and {radius_ft: max_angle}
        grid: dict[float, dict[float, float]] = {}
        amax: dict[float, float] = {}
        for top, xc, lbs in caps:
            r = nearest_radius(top)
            if r is None:
                continue
            grid.setdefault(nearest_boom(xc), {})[r] = lbs
        for top, xc, deg in angles:
            r = nearest_radius(top)
            if r is None:
                continue
            b = nearest_boom(xc)
            amax[b] = max(amax.get(b, 0.0), deg)

        # Build boom configs (metric).
        boom_configs = []
        for boom_ft in sorted(grid):
            pts = sorted(grid[boom_ft].items())
            boom_m = ft_to_m(boom_ft)
            ang = amax.get(boom_ft, 70.0)
            tip_h = round(PIVOT_HEIGHT_M + boom_m * math.sin(math.radians(ang)), 1)
            boom_configs.append(
                {
                    "boom_length_m": round(boom_m, 1),
                    "max_tip_height_m": tip_h,
                    "points": [
                        {
                            "radius_m": round(ft_to_m(r), 2),
                            "capacity_t": round(pounds_to_tonnes(lbs), 2),
                        }
                        for r, lbs in pts
                    ],
                }
            )

        max_cap = round(
            max(pounds_to_tonnes(v) for d in grid.values() for v in d.values()), 1
        )
        max_boom = round(ft_to_m(max(grid)), 1)

    return {
        "manufacturer": manufacturer,
        "model": model,
        "type": "Rough Terrain",
        "max_capacity_t": max_cap,
        "max_boom_m": max_boom,
        "counterweight": counterweight,
        "source_pdf": pdf_path.name,
        "notes": f"Main-boom chart, page {pi + 1}. Tip heights APPROXIMATE (from max boom angle).",
        "data_status": "VERIFIED from source PDF via pdfplumber (capacities exact; heights approx)",
        "boom_configs": boom_configs,
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("pdf", type=Path)
    ap.add_argument("--manufacturer", required=True)
    ap.add_argument("--model", required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args(argv)

    data = parse(args.pdf, args.manufacturer, args.model)
    args.out.write_text(json.dumps(data, indent=2), encoding="utf-8")
    n = sum(len(b["points"]) for b in data["boom_configs"])
    print(
        f"Wrote {args.out} : {len(data['boom_configs'])} boom configs, {n} points, "
        f"max cap {data['max_capacity_t']} t, max boom {data['max_boom_m']} m."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
