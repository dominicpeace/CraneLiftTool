"""Render a clipped region of a PDF page to PNG at high DPI for visual reading.
Run: python ingest/_crop.py PDF PAGE X0frac Y0frac X1frac Y1frac SCALE OUT
fractions are 0..1 of page width/height.
"""
import sys
from pathlib import Path

import fitz

pdf, page = sys.argv[1], int(sys.argv[2])
x0f, y0f, x1f, y1f = map(float, sys.argv[3:7])
scale = float(sys.argv[7])
out = Path(sys.argv[8])
doc = fitz.open(pdf)
r = doc[page].rect
clip = fitz.Rect(r.width * x0f, r.height * y0f, r.width * x1f, r.height * y1f)
doc[page].get_pixmap(matrix=fitz.Matrix(scale, scale), clip=clip).save(str(out))
print("page rect", r, "-> clip", clip, "->", out, out.stat().st_size, "bytes")
