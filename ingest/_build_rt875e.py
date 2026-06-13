"""Build grove_rt875e.json from the RT875E main-boom chart, transcribed visually from the
scanned PDF (data/pdfs/RT875.pdf page 6, '24 ft spread, 100%, 360 deg', capacities in pounds).

Capacities were read by eye from a high-DPI render and spot-checked; treat as approximate and
verify against the source chart. Long booms (120/128 ft) and radii > 90 ft were not transcribed
(low-capacity long-reach configs) -- omitting them is conservative for a quick-check tool.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
import sys

sys.path.insert(0, str(ROOT))
from crane_tool.units import ft_to_m, pounds_to_tonnes  # noqa: E402

PIVOT_HEIGHT_M = 2.4

# boom_ft -> {radius_ft: capacity_lb}
GRID = {
    41.3: {10: 150000, 12: 150000, 15: 130000, 20: 100000, 25: 80650, 30: 59050},
    50: {10: 124000, 12: 124000, 15: 124000, 20: 99650, 25: 80250, 30: 58150, 35: 43250, 40: 33600},
    60: {10: 105500, 12: 105500, 15: 104000, 20: 85900, 25: 72550, 30: 57850, 35: 43000, 40: 33400,
         45: 26600, 50: 21600},
    70: {12: 59500, 15: 59500, 20: 59500, 25: 57050, 30: 49300, 35: 42600, 40: 32950, 45: 26200,
         50: 21150, 55: 17250, 60: 14200},
    80: {15: 42100, 20: 42100, 25: 42100, 30: 42100, 35: 38150, 40: 33750, 45: 27400, 50: 22450,
         55: 18650, 60: 15600, 65: 13100, 70: 11050},
    90: {15: 42000, 20: 42000, 25: 42000, 30: 39050, 35: 34100, 40: 30050, 45: 26750, 50: 23250,
         55: 19400, 60: 16400, 65: 13850, 70: 11800, 75: 10000, 80: 8540},
    100: {20: 39650, 25: 39650, 30: 36150, 35: 31350, 40: 27500, 45: 24400, 50: 21850, 55: 19700,
          60: 17050, 65: 14550, 70: 12450, 75: 10700, 80: 9170, 85: 7850, 90: 6710},
    110: {20: 31950, 25: 31950, 30: 31950, 35: 29300, 40: 25650, 45: 22700, 50: 20250, 55: 18200,
          60: 16450, 65: 14950, 70: 12900, 75: 11200, 80: 9670, 85: 8360, 90: 7210},
}
# Highest charted boom angle per boom length (deg), used to approximate max tip height.
MAX_ANGLE = {41.3: 71, 50: 74.5, 60: 77.5, 70: 78, 80: 78, 90: 78, 100: 78, 110: 78}

boom_configs = []
for boom_ft in sorted(GRID):
    boom_m = ft_to_m(boom_ft)
    ang = MAX_ANGLE[boom_ft]
    tip = round(PIVOT_HEIGHT_M + boom_m * math.sin(math.radians(ang)), 1)
    pts = [
        {"radius_m": round(ft_to_m(r), 2), "capacity_t": round(pounds_to_tonnes(lb), 2)}
        for r, lb in sorted(GRID[boom_ft].items())
    ]
    boom_configs.append(
        {"boom_length_m": round(boom_m, 1), "max_tip_height_m": tip, "points": pts}
    )

data = {
    "manufacturer": "Grove",
    "model": "RT875E",
    "type": "Rough Terrain",
    "max_capacity_t": round(max(pounds_to_tonnes(v) for d in GRID.values() for v in d.values()), 1),
    "max_boom_m": round(ft_to_m(max(GRID)), 1),
    "counterweight": "18,000 lb counterweight, 24 ft outrigger spread, 100% / 360 deg",
    "source_pdf": "RT875.pdf",
    "notes": "Main-boom chart (RT875.pdf on source site contains the RT875E chart), page 6. "
    "Booms 120/128 ft and radii >90 ft omitted. Tip heights APPROXIMATE (from max boom angle).",
    "data_status": "TRANSCRIBED from scanned PDF via high-DPI visual reading; spot-checked. "
    "Capacities approximate - verify against source chart.",
    "boom_configs": boom_configs,
}

out = ROOT / "data" / "cranes" / "grove_rt875e.json"
out.write_text(json.dumps(data, indent=2), encoding="utf-8")
n = sum(len(b["points"]) for b in boom_configs)
print(f"Wrote {out}: {len(boom_configs)} boom configs, {n} points, "
      f"max cap {data['max_capacity_t']} t (= {max(max(d.values()) for d in GRID.values())} lb), "
      f"max boom {data['max_boom_m']} m.")
