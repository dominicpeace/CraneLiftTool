"""Download Grove GRT rough-terrain product guides (manitowoc.com) and parse into the library.

Prefers metric guides; converts the imperial-only ones (GRT765, GRT780). Models are tagged
'Rough Terrain'. Media IDs discovered from each model's product page. Run from project root:

    python ingest/batch_grt.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from ingest.parse_grove_metric import parse as parse_metric  # noqa: E402
from ingest.parse_gmk_imperial import parse as parse_imperial  # noqa: E402

PDF_DIR = ROOT / "data" / "pdfs" / "manitowoc"
OUT_DIR = ROOT / "data" / "cranes"
BASE = "https://www.manitowoc.com/media/{}/download"

# model -> (media id, "metric"|"imperial"). GRT655 and GRT655L share one guide.
MODELS = {
    "GRT540": (17939, "metric"),
    "GRT655": (16207, "metric"),
    "GRT655L": (16207, "metric"),
    "GRT765": (17684, "imperial"),
    "GRT780": (17520, "imperial"),
    "GRT8100-1": (16438, "metric"),
    "GRT8120": (16208, "metric"),
    "GRT9165": (12215, "metric"),
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
    for model, (media_id, kind) in MODELS.items():
        pdf = PDF_DIR / f"{model}-{kind}.pdf"
        try:
            if not pdf.exists():
                download(media_id, pdf)
            parser = parse_metric if kind == "metric" else parse_imperial
            data = parser(pdf, "Grove", model)
            data["type"] = "Rough Terrain"
            (OUT_DIR / f"{slug(model)}.json").write_text(json.dumps(data, indent=2), encoding="utf-8")
            n = sum(len(b["points"]) for b in data["boom_configs"])
            rows.append((model, kind, data["max_capacity_t"], data["max_boom_m"],
                         len(data["boom_configs"]), n, "ok"))
        except (Exception, SystemExit) as exc:  # parsers raise SystemExit on failure
            rows.append((model, kind, 0, 0, 0, 0, f"FAILED: {exc}"))

    print(f"{'model':<12}{'src':>9}{'maxcap_t':>9}{'boom_m':>8}{'cfgs':>6}{'pts':>6}  status")
    for m, k, cap, boom, cfgs, n, st in rows:
        print(f"{m:<12}{k:>9}{cap:>9}{boom:>8}{cfgs:>6}{n:>6}  {st}")
    print(f"\n{sum(1 for r in rows if r[6] == 'ok')}/{len(rows)} parsed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
