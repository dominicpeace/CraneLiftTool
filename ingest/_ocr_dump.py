"""OCR one PDF page and dump tokens (text,x,y,score) to a UTF-8 JSON file.
Run: python ingest/_ocr_dump.py data/pdfs/RT875.pdf 6 400 _rt875_p6_tokens.json
"""
import json
import sys
from pathlib import Path

import fitz
import numpy as np
from rapidocr_onnxruntime import RapidOCR

pdf, page, dpi, out = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), Path(sys.argv[4])
engine = RapidOCR()
doc = fitz.open(pdf)
pix = doc[page].get_pixmap(dpi=dpi)
img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
if pix.n == 4:
    img = img[:, :, :3]
result, _ = engine(img)
toks = []
for box, text, score in result or []:
    xs = [p[0] for p in box]
    ys = [p[1] for p in box]
    toks.append(
        {
            "text": text,
            "x": round(sum(xs) / 4, 1),
            "y": round(sum(ys) / 4, 1),
            "x0": round(min(xs), 1),
            "x1": round(max(xs), 1),
            "score": round(float(score), 2),
        }
    )
out.write_text(json.dumps({"w": pix.width, "h": pix.height, "tokens": toks}, indent=1), "utf-8")
print(f"{len(toks)} tokens, image {pix.width}x{pix.height} -> {out}")
