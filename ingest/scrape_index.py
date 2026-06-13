"""Scrape the reliablecraneservice load-chart index into data/index.csv.

Usage:
    python ingest/scrape_index.py [--out data/index.csv]

Best-effort HTML parse of the public listing table. The site layout can change; if the table
structure shifts, adjust the row/cell selectors below. Capacity is in US short tons and boom/jib
lengths in feet, as published.
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.request import Request, urlopen

SOURCE_URL = "https://www.reliablecraneservice.com/all-load-charts"
DEFAULT_OUT = Path(__file__).resolve().parent.parent / "data" / "index.csv"
PDF_RE = re.compile(r'href="([^"]*crane_charts/[^"]+\.pdf)"', re.IGNORECASE)


def fetch(url: str) -> str:
    req = Request(url, headers={"User-Agent": "Mozilla/5.0 (crane-lift-tool ingest)"})
    with urlopen(req, timeout=30) as resp:  # noqa: S310 - fixed trusted host
        charset = resp.headers.get_content_charset() or "utf-8"
        return resp.read().decode(charset, errors="replace")


class _TableRowParser(HTMLParser):
    """Collect text cells per <tr> so we can map them to columns heuristically."""

    def __init__(self) -> None:
        super().__init__()
        self.rows: list[list[str]] = []
        self._row: list[str] | None = None
        self._cell: list[str] | None = None

    def handle_starttag(self, tag, attrs):
        if tag == "tr":
            self._row = []
        elif tag in ("td", "th") and self._row is not None:
            self._cell = []

    def handle_endtag(self, tag):
        if tag in ("td", "th") and self._cell is not None and self._row is not None:
            self._row.append(" ".join("".join(self._cell).split()))
            self._cell = None
        elif tag == "tr" and self._row is not None:
            if any(c.strip() for c in self._row):
                self.rows.append(self._row)
            self._row = None

    def handle_data(self, data):
        if self._cell is not None:
            self._cell.append(data)


def parse(html: str) -> list[dict]:
    """Extract crane rows from the page. Falls back gracefully on layout drift."""
    parser = _TableRowParser()
    parser.feed(html)
    pdf_links = PDF_RE.findall(html)

    records: list[dict] = []
    link_idx = 0
    for cells in parser.rows:
        # Expect rows roughly like: [model, capacity, boom, jib, "Download"].
        nums = [c for c in cells if re.fullmatch(r"\d+(\.\d+)?", c.strip())]
        if len(nums) < 2 or not cells:
            continue
        model = cells[0].strip()
        if not model or model.lower() in ("model", "manufacturer"):
            continue
        pdf = pdf_links[link_idx] if link_idx < len(pdf_links) else ""
        link_idx += 1
        records.append(
            {
                "manufacturer": "",  # not reliably separable from model in this table
                "model": model,
                "type": "",
                "max_capacity_ton": nums[0] if len(nums) > 0 else "",
                "max_boom_ft": nums[1] if len(nums) > 1 else "",
                "max_jib_ft": nums[2] if len(nums) > 2 else "",
                "pdf_url": pdf,
            }
        )
    return records


def write_csv(records: list[dict], out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "manufacturer",
        "model",
        "type",
        "max_capacity_ton",
        "max_boom_ft",
        "max_jib_ft",
        "pdf_url",
    ]
    with out.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows(records)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--url", default=SOURCE_URL)
    args = ap.parse_args(argv)

    print(f"Fetching {args.url} ...")
    html = fetch(args.url)
    records = parse(html)
    if not records:
        print(
            "No rows parsed — the site layout may have changed. Inspect the HTML and adjust the "
            "selectors in scrape_index.py.",
            file=sys.stderr,
        )
        return 1
    write_csv(records, args.out)
    print(f"Wrote {len(records)} rows to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
