"""Probe a PDF: report page count, text length per page, table count, and a text sample.
Run: python ingest/_probe.py data/pdfs/<file>.pdf
"""
import sys
from pathlib import Path

import pdfplumber

path = Path(sys.argv[1])
with pdfplumber.open(str(path)) as pdf:
    print(f"=== {path.name}  ({len(pdf.pages)} pages) ===")
    for i, page in enumerate(pdf.pages):
        text = page.extract_text() or ""
        tables = page.extract_tables() or []
        print(f"page {i}: text_chars={len(text):5d}  tables={len(tables)}")
    # Find the page with the most digits (likely the load chart) and dump a sample.
    best_i, best_score, best_text = -1, -1, ""
    for i, page in enumerate(pdf.pages):
        t = page.extract_text() or ""
        score = sum(c.isdigit() for c in t)
        if score > best_score:
            best_i, best_score, best_text = i, score, t
    print(f"\n--- densest-numeric page {best_i} (digit_count={best_score}), first 1500 chars ---")
    print(best_text[:1500])
