"""Matplotlib load-chart figure with the lift's operating point marked."""

from __future__ import annotations

from typing import Optional

import matplotlib

matplotlib.use("Agg")  # headless backend; Streamlit renders the Figure object directly.
import matplotlib.pyplot as plt
from matplotlib.figure import Figure

from .models import LiftRequest, LiftResult
from .selector import SAFE_UTILIZATION, required_height


def plot_load_chart(result: LiftResult, req: LiftRequest) -> Figure:
    """Build a capacity-vs-radius load-chart figure for the evaluated crane.

    Draws every boom-length curve faintly, highlights the boom config used for the verdict,
    overlays the 90% (safe-working) line for that curve, and marks the operating point in
    green (suitable) or red (not suitable).
    """
    crane = result.crane
    fig, ax = plt.subplots(figsize=(8, 5))

    # All boom-length curves (faint context).
    for cfg in crane.boom_configs:
        radii = [p.radius_m for p in cfg.points]
        caps = [p.capacity_t for p in cfg.points]
        highlighted = result.boom_length_m is not None and abs(
            cfg.boom_length_m - result.boom_length_m
        ) < 1e-6
        if highlighted:
            ax.plot(
                radii,
                caps,
                "-o",
                color="#1f4e79",
                linewidth=2.4,
                markersize=4,
                label=f"Boom {cfg.boom_length_m:.0f} m (used)",
                zorder=4,
            )
            # 90% safe-working line for the highlighted curve.
            safe = [c * SAFE_UTILIZATION for c in caps]
            ax.plot(
                radii,
                safe,
                "--",
                color="#c0504d",
                linewidth=1.5,
                label=f"{SAFE_UTILIZATION * 100:.0f}% limit",
                zorder=3,
            )
        else:
            ax.plot(radii, caps, "-", color="#b8c4d0", linewidth=1.0, zorder=1)

    # Operating point.
    radius = result.radius_m
    load = req.load_t
    point_color = "#2e7d32" if result.suitable else "#c62828"
    ax.scatter(
        [radius],
        [load],
        s=120,
        color=point_color,
        edgecolors="black",
        linewidths=1.0,
        zorder=6,
        label=f"Lift: {load:.1f} t @ {radius:.1f} m",
    )

    # Annotate the operating point with the verdict.
    if result.capacity_t is not None and result.utilization_pct is not None:
        txt = f"{result.utilization_pct:.0f}% of {result.capacity_t:.0f} t"
    else:
        txt = "out of chart"
    ax.annotate(
        txt,
        xy=(radius, load),
        xytext=(8, 8),
        textcoords="offset points",
        fontsize=9,
        color=point_color,
        fontweight="bold",
    )

    verdict = "SUITABLE" if result.suitable else "NOT SUITABLE"
    boom_txt = (
        f"  |  boom {result.boom_length_m:.0f} m" if result.boom_length_m is not None else ""
    )
    ax.set_title(
        f"{crane.name}  —  {verdict}{boom_txt}",
        fontsize=12,
        color=point_color,
        fontweight="bold",
    )
    ax.set_xlabel("Working radius (m)")
    ax.set_ylabel("Capacity (t)")
    ax.grid(True, linestyle=":", alpha=0.6)
    ax.set_ylim(bottom=0)
    ax.set_xlim(left=0)
    ax.legend(loc="upper right", fontsize=8, framealpha=0.9)

    # Footnote: required height (height limits are enforced in selection, shown here for context).
    fig.text(
        0.01,
        0.01,
        f"Required tip height ≈ {required_height(req):.1f} m "
        f"(lift {req.vertical_lift_m:.1f} m + {req.headroom_m:.1f} m headroom)",
        fontsize=7,
        color="#555555",
    )
    fig.tight_layout()
    return fig


# Approximate boom-pivot height above ground for the schematic side view (m).
PIVOT_HEIGHT_M = 3.0


def plot_duty_point(result: LiftResult, req: LiftRequest) -> Figure:
    """Side-elevation schematic of the lift: the duty point (working radius, lift height) in space,
    with the boom drawn from the crane pivot to the hook and the hoist line down to the load.

    Coloured green if the lift is suitable, red if not. Distances are to scale (equal aspect).
    """
    radius = result.radius_m
    load_h = req.vertical_lift_m
    tip_h = required_height(req)
    color = "#2e7d32" if result.suitable else "#c62828"

    fig, ax = plt.subplots(figsize=(5, 5))

    # Ground and crane base/pivot.
    ax.axhline(0, color="#8d6e63", linewidth=1.5, zorder=1)
    ax.add_patch(plt.Rectangle((-1.4, 0), 2.8, PIVOT_HEIGHT_M, color="#9e9e9e", alpha=0.55, zorder=2))

    # Boom (pivot -> hook tip) and hoist rope (tip -> load).
    ax.plot([0, radius], [PIVOT_HEIGHT_M, tip_h], color="#1f4e79", linewidth=2.6, zorder=3,
            label=(f"boom {result.boom_length_m:.0f} m" if result.boom_length_m else "boom"))
    ax.plot([radius, radius], [tip_h, load_h], color="#666666", linewidth=1.0, linestyle=":",
            zorder=3)

    # Duty point = the load in space (working radius, lift height).
    ax.scatter([radius], [load_h], s=150, color=color, edgecolors="black", linewidths=1.0,
               zorder=5, label=f"duty point: {req.load_t:.1f} t")
    ax.annotate(
        f"{req.load_t:.1f} t @ R={radius:.1f} m, h={load_h:.1f} m",
        xy=(radius, load_h), xytext=(6, 10), textcoords="offset points",
        fontsize=9, color=color, fontweight="bold",
    )

    # Reference guide lines to the axes.
    ax.plot([radius, radius], [0, load_h], color=color, linewidth=0.8, linestyle="--", alpha=0.5)
    ax.plot([0, radius], [load_h, load_h], color=color, linewidth=0.8, linestyle="--", alpha=0.5)

    verdict = "SUITABLE" if result.suitable else "NOT SUITABLE"
    util = f"  ({result.utilization_pct:.0f}%)" if result.utilization_pct is not None else ""
    ax.set_title(f"Duty point — side view  ·  {verdict}{util}", fontsize=11, color=color,
                 fontweight="bold")
    ax.set_xlabel("Horizontal radius (m)")
    ax.set_ylabel("Height (m)")
    ax.grid(True, linestyle=":", alpha=0.5)
    ax.set_xlim(left=-2.0, right=max(radius, 1.0) * 1.25 + 2)
    ax.set_ylim(bottom=0, top=max(tip_h, load_h, PIVOT_HEIGHT_M) * 1.2 + 1)
    ax.set_aspect("equal", adjustable="box")
    ax.legend(loc="upper right", fontsize=8, framealpha=0.9)
    fig.tight_layout()
    return fig
