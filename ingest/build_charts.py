"""Render each crane's working-range diagram to a PNG and store axis calibration in its JSON.

For every crane whose source PDF is available locally, find the metric "Working range" diagram
page, auto-calibrate the axes from the integer tick labels (radius on X, height on Y), render the
page to data/charts/<slug>.png, and write a ``wr_chart`` block into the crane JSON:

    "wr_chart": {"image": "charts/<slug>.png",
                 "units": "metric",
                 "rx": [m, b],   # pixel_x = m*radius + b
                 "hy": [m, b],   # pixel_y = m*height + b
                 "r_max": <largest radius tick>, "h_max": <largest height tick>}

The app overlays the reach/lift crosshair on the real chart using this calibration. Cranes without
a detectable, calibratable working-range page are skipped (they keep the reconstructed chart).

Run (needs requirements-ingest.txt):  python ingest/build_charts.py
"""

from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from pathlib import Path

import fitz
import numpy as np
import pdfplumber

ROOT = Path(__file__).resolve().parent.parent
CRANES = ROOT / "data" / "cranes"
CHARTS = ROOT / "data" / "charts"
PDF_DIRS = [ROOT / "data" / "pdfs" / "manitowoc", ROOT / "data" / "pdfs"]
DPI = 150
SCALE = DPI / 72.0
EXCLUDE = ("jib", "luffing", "extension", "bi-fold", "bifold", "swingaway", "runner", "erection")


def find_pdf(name: str) -> Path | None:
    for d in PDF_DIRS:
        p = d / name
        if p.exists():
            return p
    return None


def find_wr_page(ppdf, target_boom: float | None = None):
    """Best metric 'Working range' diagram page (pdfplumber pdf), or (None, None).

    Strict first (telescopic-boom page with no jib/extension, that calibrates); then a relaxed pass
    over any 'working range'/'arbeitsbereich' page that calibrates, preferring non-jib pages and the
    one whose calibrated height axis best matches the crane's max boom (this separates a main-boom
    diagram from jib/extension variants). Note many main-boom range diagrams also list extension
    options, so an EXCLUDE keyword alone is only a tie-breaker, never an outright rejection.
    """
    for i, pg in enumerate(ppdf.pages):
        t = (pg.extract_text() or "").lower()
        if "working range" in t and "telescopic boom" in t and not any(k in t for k in EXCLUDE):
            if calibrate(pg):
                return i, pg
    cands = []
    for i, pg in enumerate(ppdf.pages):
        t = (pg.extract_text() or "").lower()
        if "working range" in t or "arbeitsbereich" in t:
            cal = calibrate(pg)
            if cal:
                cands.append((i, pg, any(k in t for k in EXCLUDE), cal[3]))  # cal[3] = h_max
    if not cands:
        return None, None
    pool = [c for c in cands if not c[2]] or cands
    best = min(pool, key=lambda c: abs(c[3] - target_boom) if target_boom else c[3])
    return best[0], best[1]


def _fit_axis(groups):
    """Given {key: [(value, coord), ...]}, return (slope, intercept, max_value) for the group whose
    values best span a wide linear range (the axis tick line)."""
    best = None
    for items in groups.values():
        vals = sorted(set(v for v, _ in items))
        if len(vals) < 3:
            continue
        v = np.array([p[0] for p in items], float)
        c = np.array([p[1] for p in items], float)
        m, b = np.polyfit(v, c, 1)
        span = v.max() - v.min()
        # good axis: wide value span and tight linear fit
        resid = np.abs(c - (m * v + b)).max()
        if resid > 6:
            continue
        score = span
        if best is None or score > best[0]:
            best = (score, m, b, v.max())
    return None if best is None else (best[1], best[2], best[3])


def calibrate(pg):
    """Return (rx=(m,b), hy=(m,b), r_max, h_max) in *pixel* space, or None."""
    ticks = []
    for w in pg.extract_words():
        if re.fullmatch(r"\d{1,2}", w["text"]) and int(w["text"]) % 5 == 0:
            ticks.append((int(w["text"]), (w["x0"] + w["x1"]) / 2, (w["top"] + w["bottom"]) / 2))
    if not ticks:
        return None
    by_row = defaultdict(list)  # same y  -> x-axis (value, x)
    by_col = defaultdict(list)  # same x  -> y-axis (value, y)
    for v, x, y in ticks:
        by_row[round(y / 4)].append((v, x))
        by_col[round(x / 4)].append((v, y))
    xa = _fit_axis(by_row)
    ya = _fit_axis(by_col)
    if not xa or not ya:
        return None
    mx, bx, rmax = xa
    my, by, hmax = ya
    return (
        [mx * SCALE, bx * SCALE],
        [my * SCALE, by * SCALE],
        float(rmax),
        float(hmax),
    )


def main() -> int:
    CHARTS.mkdir(parents=True, exist_ok=True)
    done = skipped = 0
    for jpath in sorted(CRANES.glob("*.json")):
        data = json.loads(jpath.read_text(encoding="utf-8"))
        pdf_name = data.get("source_pdf", "")
        pdf_path = find_pdf(pdf_name)
        # Hand-calibrated charts (graphic / unlabeled axes that can't be auto-calibrated from
        # text ticks) carry "manual": true. Never recompute or drop their calibration — just
        # re-render the PNG from the stored page so the image stays reproducible.
        manual = data.get("wr_chart") or {}
        if manual.get("manual"):
            if pdf_path:
                img = CHARTS / f"{jpath.stem}.png"
                with fitz.open(str(pdf_path)) as fpdf:
                    fpdf[manual["page"] - 1].get_pixmap(dpi=DPI).save(str(img))
                done += 1
                print(f"  ok   {data['model']:<12} page {manual['page']}  (manual, re-rendered)")
            else:
                skipped += 1
                print(f"  skip {data['model']:<12} (manual, no local PDF: {pdf_name or '-'})")
            continue
        had_chart = data.pop("wr_chart", None) is not None  # rebuild cleanly
        if not pdf_path:
            if had_chart:  # only rewrite if we removed a now-stale chart
                jpath.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
            skipped += 1
            print(f"  skip {data['model']:<12} (no local PDF: {pdf_name or '-'})")
            continue
        with pdfplumber.open(str(pdf_path)) as ppdf:
            pi, pg = find_wr_page(ppdf, data.get("max_boom_m"))
            cal = calibrate(pg) if pg is not None else None
        if cal is None:
            if had_chart:
                jpath.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
            skipped += 1
            print(f"  skip {data['model']:<12} (no calibratable working-range page)")
            continue
        rx, hy, r_max, h_max = cal
        img = CHARTS / f"{jpath.stem}.png"
        with fitz.open(str(pdf_path)) as fpdf:
            fpdf[pi].get_pixmap(dpi=DPI).save(str(img))
        data["wr_chart"] = {"image": f"charts/{img.name}", "page": pi + 1, "units": "metric",
                            "rx": [round(rx[0], 4), round(rx[1], 2)],
                            "hy": [round(hy[0], 4), round(hy[1], 2)],
                            "r_max": r_max, "h_max": h_max}
        jpath.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        done += 1
        print(f"  ok   {data['model']:<12} page {pi + 1}  rmax={r_max:.0f} hmax={h_max:.0f}")
    print(f"\n{done} charts built, {skipped} skipped.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
