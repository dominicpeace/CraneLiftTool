import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import pdfplumber
from ingest.parse_grove_metric import _header_line, _lines, _max_capacity, EXCLUDE

pdf_path = sys.argv[1]
with pdfplumber.open(pdf_path) as pdf:
    print(f"{Path(pdf_path).name}: {len(pdf.pages)} pages")
    for pi, page in enumerate(pdf.pages):
        text = (page.extract_text() or "")
        tl = text.lower()
        has_tel = "telescopic boom" in tl
        has_360 = "360" in tl
        excl = [k for k in EXCLUDE if k in tl]
        lines = _lines(page)
        htop, hdr = _header_line(lines)
        if has_tel and has_360 and hdr is not None:
            hdr_txt = " ".join(w["text"] for w in hdr)[:70]
            print(f" p{pi}: tel={has_tel} 360={has_360} excl={excl} maxcap={_max_capacity(lines):.1f}"
                  f"  hdr='{hdr_txt}'")
