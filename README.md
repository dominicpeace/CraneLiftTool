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
- A load-chart plot (capacity vs working radius) with the operating point marked and a 90% line.
- An override dropdown to evaluate any other crane in the library.
- A comparison table across the whole library.

## Suitability rule

A crane is **suitable** only if `total load < 90% × rated capacity` at the required radius/height.
At or above 90% it is flagged **NOT suitable**.

## Run

```powershell
$py = "C:\Users\tyu\AppData\Local\Programs\Python\Python312\python.exe"
Set-Location "C:\Users\tyu\CraneLiftTool"
& $py -m pip install -r requirements.txt
& $py -m streamlit run app.py
```

## Tests

```powershell
& $py -m pytest tests/
```

## Crane data

The crane library lives in `data/cranes/` as one JSON file per model (metric units: metres,
tonnes), a range of Grove rough-terrain cranes. Each file's `data_status` field records its
provenance:

| Crane | Source | Status |
|---|---|---|
| RT870, RT9100, RT890E, RT880E, RT9150E | manufacturer PDF | extracted via `parse_grove_chart.py` (main-boom chart) |
| RT875E | scanned PDF (image) | transcribed by hand from a high-DPI render |
| RT9130E | — | representative; source PDF text is font-garbage, needs visual transcription |
| RT540E | — | representative; no source PDF downloaded yet |

> **Data status:** Extracted/transcribed capacities are read from the standard main-boom,
> 100% counterweight, 360° chart; tip heights are **approximate** (from max boom angle), and a
> few upward-misread points are auto-dropped. Always verify against the actual manufacturer load
> chart (see each JSON's `source_pdf` / `data_status`) before any real decision.

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
├── data/index.csv          # scraped summary specs + PDF URLs
├── ingest/                 # scrape / download / extract tooling
└── tests/                  # unit tests
```
