"""Core selection logic: working radius, capacity lookup, suitability, recommendation."""

from __future__ import annotations

import math
from typing import List, Optional, Tuple

from .models import CraneModel, LiftRequest, LiftResult

# A crane is suitable only if the load stays strictly below this fraction of rated capacity.
SAFE_UTILIZATION = 0.90

# Approximate boom-pivot height (m) used to infer which boom length places the hook at a given
# (radius, height) — i.e. to read capacity the way a working-range chart is read by hand.
PIVOT_HEIGHT_M = 3.0


def horizontal_reach(x_reach_m: float, y_reach_m: float) -> float:
    """Plan distance from the slew centre to the load = sqrt(X^2 + Y^2).

    This is the radius a crane load chart is read against (the load-chart radius).
    """
    return math.hypot(x_reach_m, y_reach_m)


def working_radius(horizontal_reach_m: float, vertical_lift_m: float) -> float:
    """3-D slant distance from the slew centre to the load = sqrt(reach^2 + lift^2).

    (User's 'working radius'.) Informational; the load chart itself is read against the horizontal
    reach, not this value.
    """
    return math.hypot(horizontal_reach_m, vertical_lift_m)


def required_height(req: LiftRequest) -> float:
    """Required tip/hook height = vertical lift + headroom allowance."""
    return req.vertical_lift_m + req.headroom_m


def best_capacity(
    crane: CraneModel, radius_m: float, height_m: float
) -> Tuple[Optional[float], Optional[float]]:
    """Capacity read the way a working-range load chart is read by hand.

    The relevant boom is the one whose tip sits at the duty point — its length is approximately
    ``sqrt(radius^2 + (height - pivot)^2)`` — evaluated at the working radius. Returns
    ``(capacity_t, boom_length_m)``, or ``(None, None)`` if the radius is off the chart or the
    height cannot be reached at that radius.
    """
    # Distance from the boom pivot to the duty point. The boom must span at least this to place the
    # tip at (radius, height); a shorter boom simply cannot reach that height at that radius, however
    # far its capacity table extends.
    needed_len = math.hypot(radius_m, max(height_m - PIVOT_HEIGHT_M, 0.0))
    cands = [
        cfg
        for cfg in crane.boom_configs
        if cfg.min_radius_m <= radius_m <= cfg.max_radius_m  # capacity is charted at this radius
        and cfg.boom_length_m >= needed_len - 1e-6           # AND long enough to reach the height
    ]
    if not cands:
        return None, None
    # Read capacity from the shortest boom that reaches the point: its arc passes through (or just
    # above) the duty point, exactly how a working-range chart is read by hand. (Among booms long
    # enough to reach, the shortest is also the closest match to the duty-point geometry.)
    best = min(cands, key=lambda c: c.boom_length_m)
    return best.capacity_at(radius_m), best.boom_length_m


def evaluate_crane(crane: CraneModel, req: LiftRequest) -> LiftResult:
    """Evaluate a single crane against a lift request."""
    radius = horizontal_reach(req.x_reach_m, req.y_reach_m)
    height = required_height(req)
    capacity, boom = best_capacity(crane, radius, height)

    if capacity is None:
        # Distinguish "radius off the chart" from "can't reach that height at this radius".
        radius_charted = any(
            c.min_radius_m <= radius <= c.max_radius_m for c in crane.boom_configs
        )
        if not radius_charted:
            reason = f"Horizontal reach {radius:.1f} m is outside the load chart."
        else:
            reason = (
                f"Cannot reach {height:.1f} m height at {radius:.1f} m radius "
                f"(would need a longer boom than charted)."
            )
        return LiftResult(
            crane=crane,
            radius_m=radius,
            required_height_m=height,
            capacity_t=None,
            boom_length_m=None,
            utilization=None,
            suitable=False,
            reason=reason,
        )

    utilization = req.load_t / capacity
    suitable = utilization < SAFE_UTILIZATION
    if suitable:
        reason = (
            f"OK - {utilization * 100:.0f}% of rated capacity "
            f"({req.load_t:.1f} t of {capacity:.1f} t)."
        )
    else:
        reason = (
            f"NOT suitable - {utilization * 100:.0f}% of rated capacity "
            f"(>= {SAFE_UTILIZATION * 100:.0f}% limit)."
        )

    return LiftResult(
        crane=crane,
        radius_m=radius,
        required_height_m=height,
        capacity_t=capacity,
        boom_length_m=boom,
        utilization=utilization,
        suitable=suitable,
        reason=reason,
    )


def evaluate_all(cranes: List[CraneModel], req: LiftRequest) -> List[LiftResult]:
    """Evaluate every crane in the library against the request."""
    return [evaluate_crane(c, req) for c in cranes]


def recommend(cranes: List[CraneModel], req: LiftRequest) -> Optional[LiftResult]:
    """Pick the smallest-class crane that is suitable.

    Among suitable cranes choose the lowest ``max_capacity_t`` (avoid over-craning); tie-break by
    lowest utilization (most margin). Returns ``None`` if no crane in the library is suitable.
    """
    suitable = [r for r in evaluate_all(cranes, req) if r.suitable]
    if not suitable:
        return None
    suitable.sort(key=lambda r: (r.crane.max_capacity_t, r.utilization))
    return suitable[0]
