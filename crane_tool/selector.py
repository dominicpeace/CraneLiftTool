"""Core selection logic: working radius, capacity lookup, suitability, recommendation."""

from __future__ import annotations

import math
from typing import List, Optional, Tuple

from .models import CraneModel, LiftRequest, LiftResult

# A crane is suitable only if the load stays strictly below this fraction of rated capacity.
SAFE_UTILIZATION = 0.90


def working_radius(x_reach_m: float, y_reach_m: float) -> float:
    """Combine horizontal X and Y reach into a working radius R = sqrt(X^2 + Y^2)."""
    return math.hypot(x_reach_m, y_reach_m)


def required_height(req: LiftRequest) -> float:
    """Required tip/hook height = vertical lift + headroom allowance."""
    return req.vertical_lift_m + req.headroom_m


def best_capacity(
    crane: CraneModel, radius_m: float, height_m: float
) -> Tuple[Optional[float], Optional[float]]:
    """Best rated capacity this crane can offer at ``radius_m`` while reaching ``height_m``.

    Considers only boom configs that (a) can reach the required tip height and (b) chart the
    requested radius. Returns ``(capacity_t, boom_length_m)`` for the config giving the highest
    capacity, or ``(None, None)`` if no config qualifies.
    """
    best_cap: Optional[float] = None
    best_boom: Optional[float] = None
    for cfg in crane.boom_configs:
        if cfg.max_tip_height_m < height_m:
            continue
        cap = cfg.capacity_at(radius_m)
        if cap is None:
            continue
        if best_cap is None or cap > best_cap:
            best_cap = cap
            best_boom = cfg.boom_length_m
    return best_cap, best_boom


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
