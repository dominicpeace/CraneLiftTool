"""Core selection logic: working radius, capacity lookup, suitability, recommendation."""

from __future__ import annotations

import math
from typing import List, Optional, Tuple

from .models import CraneModel, LiftRequest, LiftResult

# A crane is suitable only if the load stays strictly below this fraction of rated capacity.
SAFE_UTILIZATION = 0.90


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


def _radius_window(crane: CraneModel, boom_len_m: float) -> Tuple[float, float]:
    """Charted radius window ``(min_radius, max_radius)`` for a given boom length, interpolated
    across the crane's boom configs.

    Each boom config is charted over a radius window whose small-radius end is the maximum
    boom-angle limit and whose large-radius end is the low-angle reach. Those windows shift with
    boom length, so a duty point that falls *between* two charted boom lengths is handled by
    linearly interpolating the window — instead of being dropped just because no single charted
    boom length happens to tabulate that exact radius.
    """
    cfgs = sorted(crane.boom_configs, key=lambda c: c.boom_length_m)
    bl = [c.boom_length_m for c in cfgs]

    def interp(values: List[float]) -> float:
        if boom_len_m <= bl[0]:
            return values[0]
        for i in range(1, len(bl)):
            if boom_len_m <= bl[i]:
                f = (boom_len_m - bl[i - 1]) / (bl[i] - bl[i - 1])
                return values[i - 1] + f * (values[i] - values[i - 1])
        return values[-1]

    return interp([c.min_radius_m for c in cfgs]), interp([c.max_radius_m for c in cfgs])


def _needed_boom_len(crane: CraneModel, radius_m: float, height_m: float) -> float:
    """Straight-line boom span from the boom-foot pin to a tip at ``(radius, height)``.

    The pin sits ``crane.boom_pivot_height_m`` above ground, not at ground, so the vertical leg is
    measured from there — matching the real machine and how the working-range chart is drawn.
    """
    return math.hypot(radius_m, max(height_m - crane.boom_pivot_height_m, 0.0))


def best_capacity(
    crane: CraneModel, radius_m: float, height_m: float
) -> Tuple[Optional[float], Optional[float]]:
    """Capacity read the way a working-range load chart is read by hand.

    The relevant boom is the one whose tip sits at the duty point — its length is approximately
    ``sqrt(radius^2 + height^2)``, the straight-line distance from the boom foot to the hook.
    The chart's height axis already accounts for the real boom-pivot height, so the full required
    height is used here with no assumed pivot offset. Returns ``(capacity_t, boom_length_m)``, or
    ``(None, None)`` if the radius is off the chart or the height cannot be reached at that radius.
    """
    cfgs = sorted(crane.boom_configs, key=lambda c: c.boom_length_m)
    if not cfgs:
        return None, None
    # Straight-line boom span needed to place the tip at the duty point. A shorter boom simply
    # cannot reach that height at that radius, however far its capacity table extends.
    needed_len = _needed_boom_len(crane, radius_m, height_m)
    if needed_len > cfgs[-1].boom_length_m + 1e-6:
        return None, None  # no boom long enough to reach the height at this radius
    long_enough = [c for c in cfgs if c.boom_length_m >= needed_len - 1e-6]

    # Normal read: the shortest long-enough boom whose charted window already covers this radius —
    # its arc passes through (or just above) the duty point, exactly how a chart is read by hand.
    on_radius = [
        c for c in long_enough if c.min_radius_m - 1e-6 <= radius_m <= c.max_radius_m + 1e-6
    ]
    if on_radius:
        best = on_radius[0]  # cfgs are shortest-first
        r_read = min(max(radius_m, best.min_radius_m), best.max_radius_m)
        return best.capacity_at(r_read), best.boom_length_m

    # Notch: the duty radius falls between charted boom lengths (e.g. just inside the longer booms'
    # minimum charted radius). It is reachable only if the radius lies within the interpolated
    # charted window for the needed boom length (above the max boom-angle limit, within the reach).
    min_r, max_r = _radius_window(crane, needed_len)
    if radius_m < min_r - 1e-6 or radius_m > max_r + 1e-6:
        return None, None
    # Read the shortest long-enough boom, radius clamped into its charted window — a small,
    # conservative adjustment (charted capacity only grows as the radius shrinks).
    best = long_enough[0]
    r_read = min(max(radius_m, best.min_radius_m), best.max_radius_m)
    return best.capacity_at(r_read), best.boom_length_m


def evaluate_crane(crane: CraneModel, req: LiftRequest) -> LiftResult:
    """Evaluate a single crane against a lift request."""
    radius = horizontal_reach(req.x_reach_m, req.y_reach_m)
    # Capacity is read at the LOAD position - the horizontal reach and the vertical lift height.
    # The headroom allowance is only the rope/clearance gap from the load up to the boom tip: it
    # positions the drawn boom tip (lift + headroom) but does not move the load or change the rating.
    lift_h = req.vertical_lift_m
    tip_h = required_height(req)          # boom-tip height for the sketch = lift + headroom
    capacity, boom = best_capacity(crane, radius, lift_h)

    if capacity is None:
        # Distinguish the three ways a duty point can be off the chart.
        needed_len = _needed_boom_len(crane, radius, lift_h)
        longest = max(c.boom_length_m for c in crane.boom_configs)
        if needed_len > longest + 1e-6:
            reason = (
                f"Cannot reach {lift_h:.1f} m lift at {radius:.1f} m radius "
                f"(needs a {needed_len:.1f} m boom; longest is {longest:.1f} m)."
            )
        else:
            min_r, max_r = _radius_window(crane, needed_len)
            if radius > max_r + 1e-6:
                reason = (
                    f"Horizontal reach {radius:.1f} m is beyond the load chart "
                    f"(max ~{max_r:.0f} m at this height)."
                )
            else:
                reason = (
                    f"Load at {radius:.1f} m radius is inside the minimum radius "
                    f"(~{min_r:.1f} m) for a {lift_h:.1f} m lift (boom too steep)."
                )
        return LiftResult(
            crane=crane,
            radius_m=radius,
            required_height_m=tip_h,
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
        required_height_m=tip_h,
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
