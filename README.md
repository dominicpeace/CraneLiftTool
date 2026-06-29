---
title: Crane Lifting Study
emoji: 🏗️
colorFrom: blue
colorTo: gray
sdk: streamlit
sdk_version: 1.58.0
app_file: app.py
pinned: false
---

<!-- The YAML block above configures Hugging Face Spaces (zero-login hosting). GitHub ignores it. -->

# Crane Lifting Study Tool

A quick-check tool for crane selection. Given a lift's geometry and weight, it recommends a
suitable crane model, plots the operating point on that crane's load chart, and lets you override
the recommendation with any other model in the library.

> ⚠️ **Indicative quick-check only.** This tool is for early planning and comparison. It is **not**
> a substitute for a formal lift plan or the manufacturer's actual load chart. Always verify the
> selected crane against the real chart for the correct counterweight / outrigger / boom
> configuration before lifting.

## Inputs

- **Horizontal X reach (m)** and **Horizontal Y reach (m)** — combined into a working radius
  `R = √(X² + Y²)` (horizontal distance from the crane's slew centre to the load).
- **Vertical lift (m)** — required hook/tip height.
- **Total load (t)** — weight of the load including all lifting gear (slings, hook block, spreader).

## Output

- Recommended crane (smallest class that keeps utilization below 90%).
- Rated capacity at the required radius and height, and the % utilization.
- A comparison table across the whole library (suitable models first) as a first pass.
- For a selected model, the **actual manufacturer working-range diagram** with a vertical line at
  the horizontal reach and a horizontal line at the lift height; the rated capacity is read where
  they meet — exactly how the PDF chart is read by hand. Cranes without a calibratable diagram fall
  back to a reconstructed chart. Chart images + axis calibration are built by `ingest/build_charts.py`
  and stored under `data/charts/` (with a `wr_chart` block in each crane JSON).
- An override dropdown to evaluate any other crane in the library.

## Suitability rule

A crane is **suitable** only if `total load < 90% × rated capacity` at the required radius/height.
At or above 90% it is flagged **NOT suitable**.

## Run

```powershell
$py = "C:\Users\tyu\AppData\Local\Programs\Python\Python312\python.exe"
Set-Location "C:\Users\tyu\CraneLiftTool"
& $py -m pip install -r requirements.txt   # runtime only: streamlit, matplotlib, pandas
& $py -m streamlit run app.py
```

`requirements.txt` is intentionally minimal so cloud deploys (Streamlit Community Cloud) build
fast. The PDF-ingest and OCR tooling, plus pytest, live in `requirements-ingest.txt`.

## Tests / data tooling

```powershell
& $py -m pip install -r requirements-ingest.txt   # pdfplumber, pymupdf, rapidocr, requests, pytest
& $py -m pytest tests/
```

## Crane data

The crane library lives in `data/cranes/` as one JSON file per model — **29 Grove cranes, all
metric** (metres, tonnes). Every model carries a **real manufacturer working-range chart snip**:
`ingest/build_charts.py` finds each crane's metric "Working range" diagram page in its Manitowoc
product guide, calibrates both axes, renders the page to `data/charts/<slug>.png`, and stores the
image + calibration in the JSON's `wr_chart` block. The app overlays your reach/lift crosshair on
that image. Most charts calibrate automatically from the printed tick labels. Four RT diagrams whose
axis numbers are drawn as graphics (or whose height axis is unlabeled) were calibrated from the
printed grid itself and carry `"manual": true` in `wr_chart` — `build_charts.py` re-renders their
PNGs but never overwrites that calibration.

| Class | Models | Source |
|---|---|---|
| All-terrain (GMK), 18 | GMK3050-3, GMK3060-2, GMK3060L-1, GMK4070L, GMK4080-3, GMK4080L, GMK4090-1, GMK4100L-2, GMK5120L, GMK5150-1, GMK5150L-1, GMK5150L-1e, GMK5180-1, GMK5200-1, GMK5250L-1, GMK5250XL-1, GMK6300L-1, GMK6450-1 | manitowoc.com **metric** product guides |
| Rough-terrain (GRT), 5 | GRT655, GRT655L, GRT8100-1, GRT8120, GRT9165 | manitowoc.com **metric** product guides |
| Rough-terrain (RT), 6 | RT540E, RT870, RT880E, RT890E, RT9130E, RT9150E | Grove / Manitowoc **metric** product guides |

**Metric only.** Models for which only an imperial guide (feet / US tons) was available, or whose
chart could not be read at all (scanned image, only an extension-boom diagram), were removed rather
than shipped with an imperial or unreadable chart: GMK7550, GMK5150XL, GMK5150XLe, RT875E, RT9100.
GRT540/GRT765/GRT780 were likewise excluded earlier.

**Headline `max_capacity_t`** is each crane's official maximum rated capacity, taken as the greater
of the metric product-guide cover figure and the load chart's own peak point. The cover figure
matters where the product-guide working-range chart starts at a larger radius than the rated peak
(e.g. GMK3060L-1's chart tops out at 50 t at 3 m, but it is a 60 t crane); the chart peak matters
where the chart does tabulate the tightest radius and reads slightly above the rounded cover figure
(e.g. RT540E 36 t, RT890E 81.7 t). The per-duty-point capacity used for suitability comes from the
load-chart points in `boom_configs`; for GRT9165 those points come from a reduced-configuration page
(its peak duty-point capacity reads below the 150 t headline), flagged in its `data_status`.

**Reading capacity at a duty point.** The relevant boom length is the straight-line span from the
boom foot to the hook, `√(radius² + tip_height²)`. The shortest boom that long whose charted radius
window covers the duty radius is read directly. If the duty radius falls in a gap *between* charted
boom lengths (e.g. just inside the longer booms' minimum charted radius), the reachable radius
window is interpolated across boom lengths and the read is clamped into the nearest charted radius
(a conservative capacity) — so a clearly-liftable point near the chart's steep, close-in edge is no
longer wrongly reported "out of reach".

> **Data status:** Capacities are read from the standard main-boom, 100% counterweight, 360°
> chart; tip heights are **approximate**, and a few upward-misread points are auto-dropped. Always
> verify against the actual manufacturer load chart (see each JSON's `source_pdf` / `data_status`)
> before any real decision.

### Growing the library

Source charts: <https://www.reliablecraneservice.com/all-load-charts> (US tons, feet).

```powershell
& $py ingest/scrape_index.py        # build data/index.csv from the site table
& $py ingest/download_pdfs.py       # download chosen PDFs to data/pdfs/
& $py ingest/pdf_to_chart.py <pdf>  # draft a crane JSON from a PDF (HUMAN QA REQUIRED)
```

`pdf_to_chart.py` only drafts text-table extractions; image-based charts must be entered by hand.
Every generated JSON must be reviewed against the source PDF before use.

## Layout

```
CraneLiftTool/
├── app.py                  # Streamlit UI
├── crane_tool/             # core logic (units, models, loader, selector, plot)
├── data/cranes/            # crane library (JSON, metric)
├── data/charts/            # working-range chart PNGs (committed; PDFs are git-ignored)
├── data/index.csv          # scraped summary specs + PDF URLs
├── ingest/                 # scrape / download / extract tooling (incl. build_charts.py)
└── tests/                  # unit tests
```
