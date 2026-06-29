"""Load and validate the crane library from ``data/cranes/*.json``.

JSON files store metric values directly (metres, tonnes). See ``data/cranes`` for the schema.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List

from .models import BoomConfig, ChartPoint, CraneModel

# Repo-root/data/cranes regardless of where the app is launched from.
DEFAULT_DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "cranes"


class CraneDataError(ValueError):
    """Raised when a crane JSON is malformed or fails validation."""


def _parse_boom_config(raw: dict, ctx: str) -> BoomConfig:
    try:
        points = [
            ChartPoint(radius_m=float(p["radius_m"]), capacity_t=float(p["capacity_t"]))
            for p in raw["points"]
        ]
    except (KeyError, TypeError, ValueError) as exc:
        raise CraneDataError(f"{ctx}: bad chart points ({exc})") from exc

    if len(points) < 2:
        raise CraneDataError(f"{ctx}: a boom config needs at least 2 chart points")

    try:
        return BoomConfig(
            boom_length_m=float(raw["boom_length_m"]),
            max_tip_height_m=float(raw["max_tip_height_m"]),
            points=points,
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise CraneDataError(f"{ctx}: bad boom config ({exc})") from exc


def parse_crane(raw: dict, ctx: str = "<crane>") -> CraneModel:
    """Build a :class:`CraneModel` from a parsed JSON dict."""
    try:
        configs = [
            _parse_boom_config(bc, f"{ctx} boom#{i}")
            for i, bc in enumerate(raw["boom_configs"])
        ]
    except KeyError as exc:
        raise CraneDataError(f"{ctx}: missing 'boom_configs'") from exc

    if not configs:
        raise CraneDataError(f"{ctx}: no boom configs")

    try:
        return CraneModel(
            manufacturer=str(raw["manufacturer"]),
            model=str(raw["model"]),
            type=str(raw.get("type", "")),
            max_capacity_t=float(raw["max_capacity_t"]),
            max_boom_m=float(raw["max_boom_m"]),
            boom_configs=configs,
            counterweight=str(raw.get("counterweight", "")),
            source_pdf=str(raw.get("source_pdf", "")),
            notes=str(raw.get("notes", "")),
            data_status=str(raw.get("data_status", "")),
            wr_chart=raw.get("wr_chart"),
            outrigger_width_mm=(
                float(raw["outrigger_width_mm"]) if raw.get("outrigger_width_mm") is not None else None
            ),
            tail_swing_radius_mm=(
                float(raw["tail_swing_radius_mm"]) if raw.get("tail_swing_radius_mm") is not None else None
            ),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise CraneDataError(f"{ctx}: bad crane fields ({exc})") from exc


def load_library(data_dir: Path | str = DEFAULT_DATA_DIR) -> List[CraneModel]:
    """Load every ``*.json`` crane in ``data_dir``, sorted by max capacity."""
    data_dir = Path(data_dir)
    if not data_dir.is_dir():
        raise CraneDataError(f"crane data directory not found: {data_dir}")

    cranes: List[CraneModel] = []
    for path in sorted(data_dir.glob("*.json")):
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise CraneDataError(f"{path.name}: invalid JSON ({exc})") from exc
        cranes.append(parse_crane(raw, ctx=path.name))

    if not cranes:
        raise CraneDataError(f"no crane JSON files found in {data_dir}")

    cranes.sort(key=lambda c: c.max_capacity_t)
    return cranes


def library_by_name(data_dir: Path | str = DEFAULT_DATA_DIR) -> Dict[str, CraneModel]:
    """Return the library keyed by display name (e.g. 'Grove RT890E')."""
    return {c.name: c for c in load_library(data_dir)}
