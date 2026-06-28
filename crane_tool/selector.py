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


def working_radius(x_reach_m: float, y_reach_m: float) -> float:
    """Combine horizontal X and Y reach into a working radius R = sqrt(X^2 + Y^2)."""
    return math.hypot(x_reach_m, y_reach_m)


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
    needed_len = math.hypot(radius_m, max(height_m - PIVOT_HEIGHT_M, 0.0))
    cands = [
        cfg
        for cfg in crane.boom_configs
        if cfg.boom_length_m >= radius_m and cfg.min_radius_m <= radius_m <= cfg.max_radius_m
    ]
    if not cands:
        return None, None
    # If even the longest boom that charts this radius is well short of the geometry needed to put
    # the hook at the required height, the lift is out of reach at this radius.
    if needed_len > max(c.boom_length_m for c in cands) + 2.0:
        return None, None
    # The boom whose length best matches the duty-point geometry (tip at radius/height).
    best = min(cands, key=lambda c: abs(c.boom_length_m - needed_len))
    return best.capacity_at(radius_m), best.boom_length_m


def evaluate_crane(crane: CraneModel, req: LiftRequest) -> LiftResult:
    """Evaluate a single crane against a lift request."""
    radius = working_radius(req.x_reach_m, req.y_reach_m)
    height = required_height(req)
    capacity, boom = best_capacity(crane, radius, height)

    if capacity is None:
        # Distinguish "can't reach the height" from "radius off the chart" for a useful message.
        reaches_height = any(c.max_tip_height_m >= height for c in crane.boom_configs)
        if not reaches_height:
            reason = f"Cannot reach required height of {height:.1f} m."
        else:
            reason = f"Working radius {radius:.1f} m is outside the load chart."
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
