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


def geometry_sketch(reach_m: float, lift_m: float) -> Figure:
    """Small elevation sketch defining horizontal reach, vertical lift and working radius."""
    r = max(reach_m, 0.1)
    h = max(lift_m, 0.1)
    fig, ax = plt.subplots(figsize=(3.2, 2.4))
    # Crane at origin; load at (reach, lift).
    ax.plot([0, r], [0, 0], color="#888", linewidth=1.2)            # horizontal reach
    ax.plot([r, r], [0, h], color="#888", linewidth=1.2)            # vertical lift
    ax.plot([0, r], [0, h], color="#d32f2f", linewidth=1.8)         # working radius (slant)
    ax.scatter([0], [0], s=40, color="#1f4e79", zorder=5)
    ax.scatter([r], [h], s=60, color="#2e7d32", zorder=5)
    ax.annotate("crane\ncentre", (0, 0), xytext=(4, 6), textcoords="offset points", fontsize=7)
    ax.annotate("load", (r, h), xytext=(4, 2), textcoords="offset points", fontsize=7,
                color="#2e7d32")
    ax.text(r / 2, -0.12 * h, "horizontal reach\n= √(X²+Y²)", ha="center", va="top", fontsize=7)
    ax.text(r * 1.02, h / 2, "vertical\nlift (Z)", ha="left", va="center", fontsize=7)
    ax.text(r * 0.45, h * 0.62, "working radius\n= √(reach²+lift²)", ha="center", va="bottom",
            fontsize=7, color="#d32f2f", rotation=0)
    ax.set_xlim(-0.15 * r, r * 1.35)
    ax.set_ylim(-0.35 * h, h * 1.25)
    ax.set_aspect("equal", adjustable="box")
    ax.axis("off")
    fig.tight_layout()
    return fig


def plot_real_chart(result: LiftResult, req: LiftRequest, image_path: str) -> Figure:
    """Overlay the reach/lift crosshair on the crane's actual working-range diagram (PNG).

    Uses the axis calibration in ``result.crane.wr_chart`` (pixel = m*value + b for radius and
    height) to place a vertical line at the working radius and a horizontal line at the lift height,
    marking the duty point — exactly how the chart is read by hand.
    """
    cal = result.crane.wr_chart
    rx, hy = cal["rx"], cal["hy"]
    reach, lift = result.radius_m, req.vertical_lift_m
    color = "#1faa00" if result.suitable else "#d32f2f"

    img = plt.imread(image_path)
    h_px, w_px = img.shape[0], img.shape[1]
    fig, ax = plt.subplots(figsize=(7.6, 7.6 * h_px / w_px))
    ax.imshow(img)

    x_reach = rx[0] * reach + rx[1]
    y_lift = hy[0] * lift + hy[1]
    y_base = hy[1]                          # height = 0
    x_left = rx[0] * cal["r_max"] + rx[1]   # left edge (max radius tick)
    ax.plot([x_reach, x_reach], [y_base, y_lift], color="#d32f2f", linewidth=1.8, zorder=5)
    ax.plot([x_reach, x_left], [y_lift, y_lift], color="#d32f2f", linewidth=1.8, zorder=5)
    ax.scatter([x_reach], [y_lift], s=120, color=color, edgecolors="black", linewidths=1.2, zorder=6)
    cap_txt = f"{result.capacity_t:.1f} t" if result.capacity_t is not None else "out of chart"
    ax.annotate(f"  {cap_txt}", (x_reach, y_lift), color=color, fontsize=13, fontweight="bold",
                zorder=7)

    verdict = "SUITABLE" if result.suitable else "NOT SUITABLE"
    util = f" · {result.utilization_pct:.0f}% used" if result.utilization_pct is not None else ""
    ax.set_title(f"{result.crane.name}  ·  reach {reach:.1f} m × lift {lift:.1f} m  →  {cap_txt}"
                 f"  ({verdict}{util})", fontsize=10.5, color=color, fontweight="bold")
    ax.set_xlim(0, w_px)
    ax.set_ylim(h_px, 0)
    ax.axis("off")
    fig.tight_layout()
    return fig


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
    ax.set_xlabel("Horizontal reach (m)  — load-chart radius")
    ax.set_ylabel("Hook height (m)")
    ax.grid(True, linestyle=":", alpha=0.55)
    ax.set_xlim(max_r * 1.15, 0)        # radius high→low (left→right), matching a manufacturer chart
    ax.set_ylim(0, max_h * 1.12 + 1)
    ax.set_aspect("equal", adjustable="box")
    fig.text(0.01, 0.005, "Numbers on arcs = rated capacity (t) at that radius/height. "
             "Capacities exact from chart; arc geometry approximate.", fontsize=6.5, color="#666")
    fig.tight_layout()
    return fig
