"""Download Grove GMK metric product guides and parse them into the crane library.

Media IDs were discovered from each model's manitowoc.com product page (Documentation section,
'Metric' Product Guide). Run from the project root:

    python ingest/batch_gmk.py

Skips downloads already present. Writes one data/cranes/grove_<model>.json per model and prints a
summary. Excluded: GMK5150XLe (no metric guide published; electric variant of GMK5150XL) and
GMK7550 (only an imperial guide is published).
"""

from __future__ import annotations

import sys
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from ingest.parse_grove_metric import parse  # noqa: E402

PDF_DIR = ROOT / "data" / "pdfs" / "manitowoc"
OUT_DIR = ROOT / "data" / "cranes"
BASE = "https://www.manitowoc.com/media/{}/download"

# model -> media id (metric product guide)
MODELS = {
    "GMK3060-2": 15663,
    "GMK3060L-1": 15720,
    "GMK4070L": 16448,
    "GMK4080-3": 15982,
    "GMK4080L": 17013,
    "GMK4090-1": 15985,
    "GMK4100L-2": 15987,
    "GMK5120L": 15989,
    "GMK5150-1": 15992,
    "GMK5150L-1": 15995,
    "GMK5150XL": 15997,
    "GMK5150L-1e": 18553,
    "GMK5180-1": 15014,
    "GMK5200-1": 15015,
    "GMK5250L-1": 15016,
    "GMK5250XL-1": 14660,
    "GMK6300L-1": 15721,
    "GMK6450-1": 17498,
}


def slug(model: str) -> str:
    return "grove_" + model.lower().replace("-", "_")


def download(media_id: int, dest: Path) -> None:
    req = Request(BASE.format(media_id), headers={"User-Agent": "Mozilla/5.0 (crane-tool)"})
    with urlopen(req, timeout=120) as resp:  # noqa: S310
        dest.write_bytes(resp.read())


def main() -> int:
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    rows = []
    for model, media_id in MODELS.items():
        pdf = PDF_DIR / f"{model}-metric.pdf"
        try:
            if not pdf.exists():
                download(media_id, pdf)
            data = parse(pdf, "Grove", model)
            (OUT_DIR / f"{slug(model)}.json").write_text(
                __import__("json").dumps(data, indent=2), encoding="utf-8"
            )
            n = sum(len(b["points"]) for b in data["boom_configs"])
            rows.append((model, data["max_capacity_t"], data["max_boom_m"],
                         len(data["boom_configs"]), n, "ok"))
        except Exception as exc:  # noqa: BLE001
            rows.append((model, 0, 0, 0, 0, f"FAILED: {exc}"))

    print(f"{'model':<14}{'maxcap_t':>9}{'boom_m':>8}{'cfgs':>6}{'pts':>6}  status")
    for m, cap, boom, cfgs, n, st in rows:
        print(f"{m:<14}{cap:>9}{boom:>8}{cfgs:>6}{n:>6}  {st}")
    ok = sum(1 for r in rows if r[5] == "ok")
    print(f"\n{ok}/{len(rows)} parsed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
