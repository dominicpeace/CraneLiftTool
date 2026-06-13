"""Draft a crane JSON from a load-chart PDF (HUMAN QA REQUIRED).

Usage:
    python ingest/pdf_to_chart.py data/pdfs/Grove-RT870.pdf [--out data/cranes/grove_rt870.json]

This is an *assist*, not an oracle. It uses pdfplumber to pull any machine-readable tables and
emits a draft JSON skeleton (metric, with a 'data_status' flag) plus the raw extracted tables as a
comment-like sidecar. Many crane charts are images or have merged/footnoted cells that will NOT
extract cleanly — those must be transcribed by hand. ALWAYS verify every number against the source
PDF before adding a crane to the library.

Requires: pdfplumber  (pip install pdfplumber)
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from crane_tool.units import ft_to_m, pounds_to_tonnes, short_tons_to_tonnes  # noqa: E402

DEFAULT_OUT_DIR = ROOT / "data" / "cranes"


def extract_tables(pdf_path: Path) -> list[list[list[str]]]:
    try:
        import pdfplumber  # noqa: PLC0415
    except ImportError:
        print("pdfplumber is required: pip install pdfplumber", file=sys.stderr)
        raise

    tables: list[list[list[str]]] = []
    with pdfplumber.open(str(pdf_path)) as pdf:
        for page in pdf.pages:
            for tbl in page.extract_tables() or []:
                cleaned = [
                    [("" if c is None else str(c).strip()) for c in row] for row in tbl
                ]
                if any(any(cell for cell in row) for row in cleaned):
                    tables.append(cleaned)
    return tables


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


def draft_json(pdf_path: Path, tables: list[list[list[str]]]) -> dict:
    """Build a draft crane dict. Boom configs are left EMPTY for a human to fill."""
    model_guess = pdf_path.stem.replace("_", " ")
    return {
        "manufacturer": "",
        "model": model_guess,
        "type": "",
        "max_capacity_t": 0.0,
        "max_boom_m": 0.0,
        "counterweight": "TODO — record charted counterweight / outrigger config",
        "source_pdf": pdf_path.name,
        "notes": "DRAFT auto-extraction. Transcribe and verify every value from the source PDF.",
        "data_status": "DRAFT — NOT VERIFIED. Do not use until reviewed against source PDF.",
        "_extraction_hint": {
            "imperial_to_metric": "radius/boom feet→m via ft_to_m; capacity short-tons→t via "
            "short_tons_to_tonnes (or lb→t via pounds_to_tonnes)",
            "tables_found": len(tables),
        },
        "boom_configs": [],
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("pdf", type=Path)
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument(
        "--dump-tables",
        action="store_true",
        help="also write the raw extracted tables next to the JSON for manual transcription",
    )
    args = ap.parse_args(argv)

    if not args.pdf.is_file():
        print(f"PDF not found: {args.pdf}", file=sys.stderr)
        return 1

    tables = extract_tables(args.pdf)
    print(f"Extracted {len(tables)} table(s) from {args.pdf.name}.")
    if not tables:
        print(
            "  No machine-readable tables found — this chart is likely image-based. "
            "Transcribe it by hand into a crane JSON.",
        )

    out = args.out or (DEFAULT_OUT_DIR / f"{_slug(args.pdf.stem)}.draft.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(draft_json(args.pdf, tables), indent=2), encoding="utf-8")
    print(f"Wrote DRAFT skeleton to {out} (boom_configs empty — fill in by hand).")

    if args.dump_tables and tables:
        dump = out.with_suffix(".tables.txt")
        lines = []
        for i, tbl in enumerate(tables):
            lines.append(f"=== TABLE {i} ===")
            lines.extend("\t".join(row) for row in tbl)
            lines.append("")
        dump.write_text("\n".join(lines), encoding="utf-8")
        print(f"Wrote raw tables to {dump} for manual transcription.")

    # Touch the conversion helpers so linters see them as intentionally available to users.
    _ = (ft_to_m, short_tons_to_tonnes, pounds_to_tonnes)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
