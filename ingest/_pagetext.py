"""Print the text of specific PDF page(s). Run: python ingest/_pagetext.py PDF [page]"""
import sys

import pdfplumber

pdf = sys.argv[1]
with pdfplumber.open(pdf) as doc:
    if len(sys.argv) > 2:
        pages = [int(sys.argv[2])]
    else:
        # auto: pages whose text has a 'Feet' or many digits
        pages = range(len(doc.pages))
    for i in pages:
        t = doc.pages[i].extract_text() or ""
        if len(sys.argv) > 2 or ("Pounds" in t and "Feet" in t):
            print(f"========== PAGE {i} ==========")
            print(t[:1800])
