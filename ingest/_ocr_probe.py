"""OCR-probe a PDF: render each page, OCR it, report digit density, dump densest page.
Run: python ingest/_ocr_probe.py data/pdfs/RT875.pdf [dpi]
"""
import sys
from pathlib import Path

import fitz
import numpy as np
from rapidocr_onnxruntime import RapidOCR

path = Path(sys.argv[1])
dpi = int(sys.argv[2]) if len(sys.argv) > 2 else 300
engine = RapidOCR()
doc = fitz.open(str(path))

best = (-1, -1, None)
for i in range(len(doc)):
    pix = doc[i].get_pixmap(dpi=dpi)
    img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
    if pix.n == 4:
        img = img[:, :, :3]
    result, _ = engine(img)
    tokens = result or []
    digits = sum(sum(c.isdigit() for c in t[1]) for t in tokens)
    print(f"page {i}: ocr_tokens={len(tokens):4d}  digit_chars={digits}")
    if digits > best[0]:
        best = (digits, i, tokens)

print(f"\n--- densest page {best[1]} (digits={best[0]}), first 60 tokens [text@(x,y)] ---")
for box, text, score in (best[2] or [])[:60]:
    x = sum(p[0] for p in box) / 4
    y = sum(p[1] for p in box) / 4
    print(f"  {text!r}@({x:.0f},{y:.0f}) s={score:.2f}")
