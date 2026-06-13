"""Create GMK5150XLe from GMK5150XL.

The GMK5150XLe is the electric-drivetrain variant of the GMK5150XL; lifting performance (load
chart) is identical and Manitowoc publishes no separate XLe load-chart guide. We mirror the
GMK5150XL chart with a note recording this.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
src = json.loads((ROOT / "data" / "cranes" / "grove_gmk5150xl.json").read_text(encoding="utf-8"))
src["model"] = "GMK5150XLe"
src["notes"] = ("Electric-drivetrain variant of GMK5150XL; lifting load chart is identical "
                "(no separate XLe guide is published). Data mirrored from GMK5150XL.")
src["data_status"] = ("MIRRORED from GMK5150XL (identical load chart; electric variant). "
                      "Verify against the manufacturer chart before use.")
out = ROOT / "data" / "cranes" / "grove_gmk5150xle.json"
out.write_text(json.dumps(src, indent=2), encoding="utf-8")
print("Wrote", out.name, "| max cap", src["max_capacity_t"], "t")
