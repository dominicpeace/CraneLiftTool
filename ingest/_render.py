"""Render a PDF page to PNG. Run: python ingest/_render.py data/pdfs/RT875.pdf 9 [dpi] [out.png]"""
import sys
from pathlib import Path

import fitz

path = Path(sys.argv[1])
pageno = int(sys.argv[2])
dpi = int(sys.argv[3]) if len(sys.argv) > 3 else 200
out = Path(sys.argv[4]) if len(sys.argv) > 4 else Path(f"_page_{pageno}.png")
doc = fitz.open(str(path))
doc[pageno].get_pixmap(dpi=dpi).save(str(out))
print("wrote", out, "size", out.stat().st_size)
