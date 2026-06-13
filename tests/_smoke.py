"""Manual end-to-end smoke test (not part of pytest). Run: python tests/_smoke.py"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from crane_tool import load_library, recommend
from crane_tool.models import LiftRequest
from crane_tool.selector import evaluate_crane, working_radius
from crane_tool.chart_plot import plot_load_chart

cranes = load_library()
print("Loaded", len(cranes), "cranes:", [c.name for c in cranes])

req = LiftRequest(x_reach_m=5.0, y_reach_m=3.0, vertical_lift_m=8.0, load_t=40.0)
print("Working radius = %.2f m" % working_radius(5.0, 3.0))

rec = recommend(cranes, req)
print(
    "RECOMMENDED: %s | cap %.1f t | util %.0f%% | boom %.0f m"
    % (rec.crane.name, rec.capacity_t, rec.utilization_pct, rec.boom_length_m)
)

out = Path(__file__).resolve().parent.parent / "smoke_chart.png"
fig = plot_load_chart(rec, req)
fig.savefig(out, dpi=80)
print("Saved", out.name, "OK")

req2 = LiftRequest(x_reach_m=20.0, y_reach_m=10.0, vertical_lift_m=30.0, load_t=150.0)
print("Overload recommend ->", recommend(cranes, req2))
r = evaluate_crane(cranes[-1], req2)
print("Biggest crane (%s) verdict: suitable=%s | %s" % (cranes[-1].name, r.suitable, r.reason))
