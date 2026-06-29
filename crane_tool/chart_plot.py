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


def _iso(wx: float, wy: float, wz: float) -> tuple[float, float]:
    """Project a 3-D world point (X horizontal, Y horizontal, Z up) to 2-D isometric screen coords.

    X runs down-right, Y up-right, Z straight up — a standard isometric view.
    """
    c = 0.8660254  # cos 30°
    return c * (wx + wy), 0.5 * (wy - wx) + wz


def _mid(a: tuple[float, float], b: tuple[float, float]) -> tuple[float, float]:
    return (a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0


def _corner(ax, v, a, b, size, color="#9aa0a6") -> None:
    """Draw a small right-angle marker at vertex ``v`` between the edges toward ``a`` and ``b``."""
    def unit(p, q):
        dx, dy = q[0] - p[0], q[1] - p[1]
        d = math.hypot(dx, dy) or 1.0
        return dx / d, dy / d

    ua, ub = unit(v, a), unit(v, b)
    p1 = (v[0] + ua[0] * size, v[1] + ua[1] * size)
    p2 = (v[0] + (ua[0] + ub[0]) * size, v[1] + (ua[1] + ub[1]) * size)
    p3 = (v[0] + ub[0] * size, v[1] + ub[1] * size)
    ax.plot([p1[0], p2[0], p3[0]], [p1[1], p2[1], p3[1]], color=color, linewidth=0.9, zorder=4)


def geometry_sketch(x_m: float, y_m: float, lift_m: float) -> Figure:
    """Isometric 3-D sketch defining the lift geometry: the two horizontal reaches X and Y on the
    ground, their resultant horizontal reach HR = √(X²+Y²), the vertical lift VL, and the working
    radius WR = √(HR²+VL²) — the slant straight from the boom pivot to the load.

    Proportions are illustrative (small legs are floored so nothing collapses); the live values are
    shown in the metric cards above the chart.
    """
    scale = max(x_m, y_m, lift_m, 1.0)
    fx = max(x_m, 0.25 * scale)      # floor lengths so a zero/small input still reads clearly
    fy = max(y_m, 0.25 * scale)
    fz = max(lift_m, 0.25 * scale)

    P = _iso(0, 0, 0)                # pivot (origin)
    C = _iso(fx, 0, 0)               # end of the X leg
    B = _iso(fx, fy, 0)             # base under the load (end of the Y leg)
    L = _iso(fx, fy, fz)            # the load

    fig, ax = plt.subplots(figsize=(3.4, 3.2))

    # Faint ground plane (pivot -> X -> base) to anchor the horizontal triangle in 3-D.
    ax.fill([P[0], C[0], B[0]], [P[1], C[1], B[1]], color="#b8c0cc", alpha=0.16, zorder=0)

    ax.plot([P[0], C[0]], [P[1], C[1]], color="#6b7280", linewidth=1.6, zorder=2)   # X leg
    ax.plot([C[0], B[0]], [C[1], B[1]], color="#6b7280", linewidth=1.6, zorder=2)   # Y leg
    ax.plot([P[0], B[0]], [P[1], B[1]], color="#1f77b4", linewidth=1.6,
            linestyle=(0, (5, 3)), zorder=3)                                        # HR (ground)
    ax.plot([B[0], L[0]], [B[1], L[1]], color="#2e9e3f", linewidth=1.6,
            linestyle=(0, (5, 3)), zorder=3)                                        # VL (vertical)
    ax.plot([P[0], L[0]], [P[1], L[1]], color="#d32f2f", linewidth=2.4, zorder=3)   # WR (slant)

    size = 0.10 * scale
    _corner(ax, C, P, B, size)       # right angle between X and Y on the ground
    _corner(ax, B, P, L, size)       # right angle between HR and VL

    ax.scatter(*P, s=46, color="#1f4e79", zorder=6)
    ax.scatter(*L, s=70, color="#2e7d32", zorder=6)

    ax.annotate("PIVOT", P, xytext=(-6, -9), textcoords="offset points", fontsize=8,
                color="#1f4e79", fontweight="bold", ha="right")
    ax.annotate("LOAD", L, xytext=(7, 3), textcoords="offset points", fontsize=8,
                color="#2e7d32", fontweight="bold")
    ax.annotate("X", _mid(P, C), xytext=(-3, -10), textcoords="offset points", fontsize=8,
                color="#444", ha="center")
    ax.annotate("Y", _mid(C, B), xytext=(9, -3), textcoords="offset points", fontsize=8, color="#444")
    ax.annotate("HR", _mid(P, B), xytext=(0, 7), textcoords="offset points", fontsize=8,
                color="#1f77b4", fontweight="bold", ha="center")
    ax.annotate("VL", _mid(B, L), xytext=(8, 0), textcoords="offset points", fontsize=8,
                color="#2e9e3f", fontweight="bold")
    ax.annotate("WR", _mid(P, L), xytext=(-14, 2), textcoords="offset points", fontsize=8,
                color="#d32f2f", fontweight="bold")

    xs, ys = [P[0], C[0], B[0], L[0]], [P[1], C[1], B[1], L[1]]
    pad = 0.34 * max(max(xs) - min(xs), max(ys) - min(ys), 1.0)
    ax.set_xlim(min(xs) - pad, max(xs) + pad)
    ax.set_ylim(min(ys) - pad, max(ys) + pad)
    ax.set_aspect("equal", adjustable="box")
    ax.axis("off")
    fig.text(0.5, 0.015, "HR = √(X² + Y²)    ·    WR = √(HR² + VL²)", ha="center", fontsize=7,
             color="#666")
    fig.tight_layout(rect=(0, 0.05, 1, 1))
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

    # Calibrated corners of the chart's plotting area (pixels). Radius increases right->left
    # (r=0 near the crane on the right); height increases bottom->top.
    x_r0 = rx[1]                                 # radius = 0  (right edge of axes)
    x_rmax = rx[0] * cal["r_max"] + rx[1]        # max radius (left edge of axes)
    y_h0 = hy[1]                                 # height = 0  (bottom of axes)
    y_hmax = hy[0] * cal["h_max"] + hy[1]        # max height (top of axes)
    x_lo, x_hi = sorted((x_rmax, x_r0))
    y_lo, y_hi = sorted((y_hmax, y_h0))
    xspan, yspan = x_hi - x_lo, y_hi - y_lo

    # Crop to the chart itself — drop the page header banner above and the hook-block table below so
    # the diagram fills the view and stays large/readable wherever the duty point falls (the old full
    # -page render left the chart tiny, worst for high-lift points near the cramped top arcs). Keep
    # the full right side for the boom-length labels and crane silhouette; pad the other edges a
    # little to retain the axis tick labels.
    left = max(0, int(x_lo - 0.08 * xspan))
    right = w_px
    top = max(0, int(y_lo - 0.12 * yspan))
    bottom = min(h_px, int(y_hi + 0.06 * yspan))
    crop = img[top:bottom, left:right]
    ch, cw = crop.shape[0], crop.shape[1]

    fig, ax = plt.subplots(figsize=(9.0, 9.0 * ch / cw))
    ax.imshow(crop)

    # Duty-point crosshair in cropped pixel coordinates.
    x_reach = rx[0] * reach + rx[1] - left
    y_lift = hy[0] * lift + hy[1] - top
    y_base = y_h0 - top                          # height = 0
    x_left = x_rmax - left                        # max-radius (left) edge of axes
    ax.plot([x_reach, x_reach], [y_base, y_lift], color="#d32f2f", linewidth=2.0, zorder=5)
    ax.plot([x_reach, x_left], [y_lift, y_lift], color="#d32f2f", linewidth=2.0, zorder=5)
    ax.scatter([x_reach], [y_lift], s=140, color=color, edgecolors="black", linewidths=1.3, zorder=6)
    cap_txt = f"{result.capacity_t:.1f} t" if result.capacity_t is not None else "out of reach"
    ax.annotate(f"  {cap_txt}", (x_reach, y_lift), color=color, fontsize=15, fontweight="bold",
                zorder=7)

    # "Out of reach" (duty point beyond the boom's coverage, so there is no rated capacity at all)
    # is a distinct verdict from "Not suitable" (reachable, but the load exceeds the safe limit).
    if result.capacity_t is None:
        tail = "OUT OF REACH"
    else:
        verdict = "SUITABLE" if result.suitable else "NOT SUITABLE"
        util = f" · {result.utilization_pct:.0f}% used" if result.utilization_pct is not None else ""
        tail = f"{cap_txt}  ({verdict}{util})"
    ax.set_title(f"{result.crane.name}  ·  reach {reach:.1f} m × lift {lift:.1f} m  →  {tail}",
                 fontsize=11, color=color, fontweight="bold")
    ax.set_xlim(0, cw)
    ax.set_ylim(ch, 0)
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
    max_h = max(lift_h, 1.0)

    for cfg in crane.boom_configs:
        length = cfg.boom_length_m
        rs, hs, caps = [], [], []
        for p in cfg.points:
            if p.radius_m >= length:  # radius beyond boom length is geometrically impossible
                continue
            rs.append(p.radius_m)
            hs.append(math.sqrt(length * length - p.radius_m * p.radius_m))
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

    cap_txt = f"{result.capacity_t:.1f} t" if result.capacity_t is not None else "out of reach"
    ax.annotate(f"  {cap_txt}", (radius, lift_h), xytext=(6, 6), textcoords="offset points",
                fontsize=11, fontweight="bold", color=color, zorder=8)

    # "Out of reach" (beyond boom coverage, no rated capacity) is distinct from "Not suitable"
    # (reachable but the load exceeds the safe limit).
    if result.capacity_t is None:
        tail = "OUT OF REACH"
    else:
        verdict = "SUITABLE" if result.suitable else "NOT SUITABLE"
        util = f" · {result.utilization_pct:.0f}% used" if result.utilization_pct is not None else ""
        tail = f"{cap_txt}  ({verdict}{util})"
    ax.set_title(
        f"{crane.name}  ·  reach {radius:.1f} m × lift {lift_h:.1f} m  →  {tail}",
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
