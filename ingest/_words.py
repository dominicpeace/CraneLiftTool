"""Dump word x-positions for a page to design column mapping.
Run: python ingest/_words.py data/pdfs/Grove-RT870.pdf 5
"""
import sys
from pathlib import Path

import pdfplumber

path = Path(sys.argv[1])
pageno = int(sys.argv[2])
with pdfplumber.open(str(path)) as pdf:
    page = pdf.pages[pageno]
    words = page.extract_words()
    # Group words into lines by rounded 'top'.
    lines = {}
    for w in words:
        key = round(w["top"] / 3) * 3
        lines.setdefault(key, []).append(w)
    for key in sorted(lines):
        row = sorted(lines[key], key=lambda w: w["x0"])
        cells = " | ".join(f'{w["text"]}@{w["x0"]:.0f}' for w in row)
        print(f"top={key:4d}: {cells}")
