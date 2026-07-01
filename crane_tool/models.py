"""Data models for cranes, lift requests, and evaluation results.

All quantities are metric: distances in metres (m), weights/capacities in metric tonnes (t).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass(frozen=True)
class ChartPoint:
    """A single (radius, capacity) point on a load-chart curve."""

    radius_m: float
    capacity_t: float


@dataclass
class BoomConfig:
    """One boom-length configuration of a crane and its capacity-vs-radius curve.

    ``max_tip_height_m`` is the maximum hook/tip height achievable in this configuration
    (from the crane's range/lift-height diagram).
    """

    boom_length_m: float
    max_tip_height_m: float
    points: List[ChartPoint] = field(default_factory=list)

    def __post_init__(self) -> None:
        # Keep points sorted by radius so interpolation is straightforward.
        self.points = sorted(self.points, key=lambda p: p.radius_m)

    @property
    def min_radius_m(self) -> float:
        return self.points[0].radius_m

    @property
    def max_radius_m(self) -> float:
        return self.points[-1].radius_m

    def capacity_at(self, radius_m: float) -> Optional[float]:
        """Linearly interpolate rated capacity at ``radius_m``.

        Returns ``None`` if the radius is outside this configuration's charted range
        (cannot extrapolate a load chart safely).
        """
        pts = self.points
        if not pts or radius_m < self.min_radius_m or radius_m > self.max_radius_m:
            return None
        # Exact / endpoint hits.
        for p in pts:
            if abs(p.radius_m - radius_m) < 1e-9:
                return p.capacity_t
        # Find the bracketing pair and interpolate.
        for lo, hi in zip(pts, pts[1:]):
            if lo.radius_m <= radius_m <= hi.radius_m:
                span = hi.radius_m - lo.radius_m
                if span <= 0:
                    return lo.capacity_t
                frac = (radius_m - lo.radius_m) / span
                return lo.capacity_t + frac * (hi.capacity_t - lo.capacity_t)
        return None  # pragma: no cover - guarded by range check above


@dataclass
class CraneModel:
    """A crane model and its full set of boom configurations."""

    manufacturer: str
    model: str
    type: str
    max_capacity_t: float
    max_boom_m: float
    boom_configs: List[BoomConfig] = field(default_factory=list)
    counterweight: str = ""
    source_pdf: str = ""
    notes: str = ""
    data_status: str = ""
    wr_chart: Optional[dict] = None  # real working-range chart image + axis calibration (if available)
    # Set-up footprint dimensions (mm), read from the guide's dimensions diagram (optional).
    outrigger_width_mm: Optional[float] = None   # fully-extended outrigger lateral span
    tail_swing_radius_mm: Optional[float] = None  # rear (tail) rotating radius of the superstructure

    @property
    def name(self) -> str:
        return f"{self.manufacturer} {self.model}"

    @property
    def min_setup_space_mm(self) -> Optional[float]:
        """Minimum set-up space = half the outrigger width + the tail-swing radius.

        The clear lateral footprint from the outrigger pad on one side to the tail-swing extreme
        on the other. ``None`` if either dimension is not recorded for this crane.
        """
        if self.outrigger_width_mm is None or self.tail_swing_radius_mm is None:
            return None
        return 0.5 * self.outrigger_width_mm + self.tail_swing_radius_mm

    @property
    def boom_pivot_height_m(self) -> float:
        """Estimated boom-foot pin height above ground (m), fitted from this crane's own data.

        Each boom length's maximum tip height is ``pivot + boom_length × sin(max boom angle)``, so a
        least-squares line through the crane's ``(boom_length, max_tip_height)`` points has the pin
        height as its intercept. Measuring the boom from this pin (not the ground) matches the real
        machine and the working-range chart, where every boom-angle line fans out from the pin.
        Falls back to an assumed ~80° max angle when there is only one boom length; clamped to a
        sane 0-5 m.
        """
        cfgs = self.boom_configs
        n = len(cfgs)
        if n == 0:
            return 0.0
        lengths = [c.boom_length_m for c in cfgs]
        heights = [c.max_tip_height_m for c in cfgs]
        mean_l = sum(lengths) / n
        sxx = sum((length - mean_l) ** 2 for length in lengths)
        if sxx < 1e-9:  # a single boom length (or all equal) can't fit a slope
            pin = min(heights) - max(lengths) * math.sin(math.radians(80.0))
        else:
            mean_h = sum(heights) / n
            slope = sum((length - mean_l) * (h - mean_h)
                        for length, h in zip(lengths, heights)) / sxx
            pin = mean_h - slope * mean_l
        return min(max(pin, 0.0), 5.0)

    @property
    def boom_foot_elev_m(self) -> float:
        """Boom-foot pin elevation used for the boom geometry (m).

        Prefers the point digitised off this crane's chart silhouette (``wr_chart['pin_elev_m']``,
        the boom-to-body hinge over the rear wheels) so the drawn boom and the capacity reading use
        the *same* pin and stay consistent; otherwise falls back to the fitted geometric pivot.
        """
        if self.wr_chart and self.wr_chart.get("pin_elev_m") is not None:
            return float(self.wr_chart["pin_elev_m"])
        return self.boom_pivot_height_m


@dataclass(frozen=True)
class LiftRequest:
    """A lift to evaluate. Inputs are metric."""

    x_reach_m: float
    y_reach_m: float
    vertical_lift_m: float
    load_t: float
    headroom_m: float = 1.5  # hook-block / clearance allowance added to required tip height


@dataclass
class LiftResult:
    """Result of evaluating one crane against a lift request."""

    crane: CraneModel
    radius_m: float
    required_height_m: float
    capacity_t: Optional[float]          # rated capacity at the radius/height (None if unreachable)
    boom_length_m: Optional[float]       # boom config that achieves capacity_t
    utilization: Optional[float]         # load_t / capacity_t (None if unreachable)
    suitable: bool
    reason: str                          # human-readable explanation of the verdict

    @property
    def utilization_pct(self) -> Optional[float]:
        return None if self.utilization is None else self.utilization * 100.0
