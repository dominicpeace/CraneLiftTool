"""Download crane load-chart PDFs listed in data/index.csv to data/pdfs/.

Usage:
    python ingest/download_pdfs.py                # download all PDFs in index.csv
    python ingest/download_pdfs.py RT890E RT875   # only models whose name contains these terms

Downloaded PDFs are git-ignored (regenerable). Existing files are skipped.
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INDEX = ROOT / "data" / "index.csv"
DEFAULT_OUT = ROOT / "data" / "pdfs"


def read_index(index: Path) -> list[dict]:
    with index.open(encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def download(url: str, dest: Path) -> bool:
    req = Request(url, headers={"User-Agent": "Mozilla/5.0 (crane-lift-tool ingest)"})
    with urlopen(req, timeout=60) as resp:  # noqa: S310
        data = resp.read()
    dest.write_bytes(data)
    return True


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("filters", nargs="*", help="optional substrings; only matching models")
    ap.add_argument("--index", type=Path, default=DEFAULT_INDEX)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = ap.parse_args(argv)

    rows = read_index(args.index)
    if args.filters:
        terms = [t.lower() for t in args.filters]
        rows = [r for r in rows if any(t in r["model"].lower() for t in terms)]

    args.out.mkdir(parents=True, exist_ok=True)
    ok = skipped = failed = 0
    for r in rows:
        url = (r.get("pdf_url") or "").strip()
        if not url:
            continue
        name = url.rsplit("/", 1)[-1]
        dest = args.out / name
        if dest.exists():
            skipped += 1
            continue
        try:
            download(url, dest)
            print(f"  downloaded {name}")
            ok += 1
        except Exception as exc:  # noqa: BLE001 - report and continue
            print(f"  FAILED {name}: {exc}", file=sys.stderr)
            failed += 1

    print(f"Done: {ok} downloaded, {skipped} skipped (exists), {failed} failed -> {args.out}")
    return 1 if failed and not ok else 0


if __name__ == "__main__":
    raise SystemExit(main())
