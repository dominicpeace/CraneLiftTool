"""Matplotlib load-chart figure with the lift's operating point marked."""

from __future__ import annotations

import math
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
    fig, ax = plt.subplots(figsize=(6.2, 3.7))

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
    """Working-range diagram (hook height vs working radius) with the duty point plotted.

    Draws one arc per boom length — the locus of hook-tip height as the boom luffs, approximated as
    height = pivot + sqrt(boom_length^2 - radius^2) over the charted radius range — and marks the
    duty point at (working radius, vertical lift), coloured green if suitable, red if not. Mirrors
    a manufacturer working-range diagram.
    """
    radius = result.radius_m
    load_h = req.vertical_lift_m
    tip_h = required_height(req)
    color = "#2e7d32" if result.suitable else "#c62828"
    crane = result.crane

    fig, ax = plt.subplots(figsize=(6.0, 4.4))
    max_h = max(tip_h, load_h, PIVOT_HEIGHT_M)
    max_r = max(radius, 1.0)

    for cfg in crane.boom_configs:
        length = cfg.boom_length_m
        r_hi = min(cfg.max_radius_m, length * 0.999)
        r_lo = min(cfg.min_radius_m, r_hi)
        if r_hi <= r_lo:
            continue
        rs = [r_lo + (r_hi - r_lo) * i / 60 for i in range(61)]
        hs = [PIVOT_HEIGHT_M + math.sqrt(max(length * length - r * r, 0.0)) for r in rs]
        max_h, max_r = max(max_h, max(hs)), max(max_r, r_hi)
        used = result.boom_length_m is not None and abs(length - result.boom_length_m) < 1e-6
        if used:
            ax.plot(rs, hs, color="#1f4e79", linewidth=2.6, zorder=4,
                    label=f"boom {length:.0f} m (used)")
        else:
            ax.plot(rs, hs, color="#b8c4d0", linewidth=1.0, zorder=1)
        # Boom-length label at the top (small-radius) end of the arc.
        ax.annotate(f"{length:.0f}", xy=(rs[0], hs[0]), fontsize=6, color="#7a8aa0",
                    ha="right", va="bottom", zorder=2)

    # Boom line to the hook and hoist line down to the load.
    ax.plot([0, radius], [PIVOT_HEIGHT_M, tip_h], color=color, linewidth=1.4, linestyle="-",
            alpha=0.7, zorder=5)
    ax.plot([radius, radius], [tip_h, load_h], color="#666666", linewidth=1.0, linestyle=":",
            zorder=5)

    # Duty point — show the load AND the crane's rated capacity at this radius/height.
    if result.capacity_t is not None:
        cap_txt = f"capacity {result.capacity_t:.1f} t"
        if result.utilization_pct is not None:
            cap_txt += f" ({result.utilization_pct:.0f}% used)"
    else:
        cap_txt = "out of chart"
    boom_txt = f", boom {result.boom_length_m:.0f} m" if result.boom_length_m else ""
    ax.scatter([radius], [load_h], s=170, color=color, edgecolors="black", linewidths=1.2,
               zorder=6, label=f"duty point: {req.load_t:.1f} t @ {radius:.1f} m")
    ax.annotate(
        f"load {req.load_t:.1f} t  ·  {cap_txt}\nR={radius:.1f} m, h={load_h:.1f} m{boom_txt}",
        xy=(radius, load_h), xytext=(8, 8), textcoords="offset points",
        fontsize=9, color=color, fontweight="bold",
    )
    ax.plot([radius, radius], [0, load_h], color=color, linewidth=0.8, linestyle="--", alpha=0.5)
    ax.plot([0, radius], [load_h, load_h], color=color, linewidth=0.8, linestyle="--", alpha=0.5)

    verdict = "SUITABLE" if result.suitable else "NOT SUITABLE"
    util = f"  ({result.utilization_pct:.0f}%)" if result.utilization_pct is not None else ""
    ax.set_title(f"Working-range diagram — duty point  ·  {verdict}{util}",
                 fontsize=12, color=color, fontweight="bold")
    ax.set_xlabel("Working radius (m)")
    ax.set_ylabel("Hook height (m)")
    ax.grid(True, linestyle=":", alpha=0.5)
    ax.set_xlim(left=0, right=max_r * 1.1 + 2)
    ax.set_ylim(bottom=0, top=max_h * 1.1 + 2)
    ax.set_aspect("equal", adjustable="box")
    ax.legend(loc="upper right", fontsize=9, framealpha=0.9)
    fig.tight_layout()
    return fig
