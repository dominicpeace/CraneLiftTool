"""Matplotlib working-range diagram with crosshair lines, mirroring how a load chart is read
by hand: draw a vertical line at the working radius and a horizontal line at the lift height; the
capacity is read where they intersect a boom-length arc.

All data is metric (SI), so the chart is always drawn in metres / tonnes.
"""

from __future__ import annotations

import math

import matplotlib

matplotlib.use("Agg")  # headless backend; Streamlit renders the Figure object directly.
import matplotlib.pyplot as plt
from matplotlib.figure import Figure

from .models import LiftRequest, LiftResult

# Approximate boom-pivot height above ground (m) for the height geometry of the arcs.
PIVOT_HEIGHT_M = 3.0


def plot_range_chart(result: LiftResult, req: LiftRequest) -> Figure:
    """Working-range diagram for one crane with the lift's crosshair lines.

    Each boom length is drawn as an arc of hook height vs working radius
    (height = pivot + sqrt(boom^2 - radius^2)), with the rated capacity labelled at every charted
    point — like the manufacturer diagram. Red crosshair lines mark the working radius and the lift
    height; the capacity the tool reads at that duty point is annotated at the intersection.
    """
    crane = result.crane
    radius = result.radius_m
    lift_h = req.vertical_lift_m
    color = "#2e7d32" if result.suitable else "#c62828"

    fig, ax = plt.subplots(figsize=(7.5, 6.0))
    max_r = max(radius, 1.0)
    max_h = max(lift_h, PIVOT_HEIGHT_M)

    for cfg in crane.boom_configs:
        length = cfg.boom_length_m
        rs, hs, caps = [], [], []
        for p in cfg.points:
            if p.radius_m >= length:  # radius beyond boom length is geometrically impossible
                continue
            rs.append(p.radius_m)
            hs.append(PIVOT_HEIGHT_M + math.sqrt(length * length - p.radius_m * p.radius_m))
            caps.append(p.capacity_t)
        if len(rs) < 2:
            continue
        used = result.boom_length_m is not None and abs(length - result.boom_length_m) < 1e-6
        ax.plot(rs, hs, "-", color="#1f4e79" if used else "#c2cedb",
                linewidth=2.4 if used else 0.8, zorder=4 if used else 1)
        # Capacity labels only on the selected boom arc (the one the duty point sits on) to keep the
        # chart readable; the other arcs stay as faint context.
        if used:
            for r, h, cap in zip(rs, hs, caps):
                ax.annotate(f"{cap:g}", (r, h), fontsize=7, color="#1f3a5f",
                            ha="center", va="bottom", zorder=5)
        # Boom-length label at the high end (smallest radius) of each arc.
        ax.annotate(f"{length:.0f} m", (rs[0], hs[0]), fontsize=6.5,
                    color="#1f4e79" if used else "#bcc7d4", ha="left", va="bottom", zorder=3)
        max_r, max_h = max(max_r, max(rs)), max(max_h, max(hs))

    # Crosshair: vertical at the working radius (down to ground), horizontal at the lift height.
    ax.plot([radius, radius], [0, lift_h], color="#d32f2f", linewidth=1.7, zorder=6)
    ax.plot([radius, max_r * 1.12], [lift_h, lift_h], color="#d32f2f", linewidth=1.7, zorder=6)
    ax.scatter([radius], [lift_h], s=90, color=color, edgecolors="black", linewidths=1.0, zorder=7)

    cap_txt = f"{result.capacity_t:.1f} t" if result.capacity_t is not None else "out of chart"
    ax.annotate(f"  {cap_txt}", (radius, lift_h), xytext=(6, 6), textcoords="offset points",
                fontsize=11, fontweight="bold", color=color, zorder=8)

    verdict = "SUITABLE" if result.suitable else "NOT SUITABLE"
    util = f" · {result.utilization_pct:.0f}% used" if result.utilization_pct is not None else ""
    ax.set_title(
        f"{crane.name}  ·  reach {radius:.1f} m × lift {lift_h:.1f} m  →  {cap_txt}"
        f"  ({verdict}{util})",
        fontsize=10.5, color=color, fontweight="bold",
    )
    ax.set_xlabel("Working radius (m)")
    ax.set_ylabel("Hook height (m)")
    ax.grid(True, linestyle=":", alpha=0.55)
    ax.set_xlim(max_r * 1.15, 0)        # radius high→low (left→right), matching a manufacturer chart
    ax.set_ylim(0, max_h * 1.12 + 1)
    ax.set_aspect("equal", adjustable="box")
    fig.text(0.01, 0.005, "Numbers on arcs = rated capacity (t) at that radius/height. "
             "Capacities exact from chart; arc geometry approximate.", fontsize=6.5, color="#666")
    fig.tight_layout()
    return fig
