"""Unit tests for radius, interpolation, recommendation, and the 90% boundary."""

from __future__ import annotations

import math
from pathlib import Path

import pytest

from crane_tool.data_loader import load_library
from crane_tool.models import BoomConfig, ChartPoint, CraneModel, LiftRequest
from crane_tool.selector import (
    SAFE_UTILIZATION,
    best_capacity,
    evaluate_crane,
    horizontal_reach,
    recommend,
    required_height,
    working_radius,
)

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "cranes"


# --- fixtures -------------------------------------------------------------

def _toy_crane(name="Toy 50", max_cap=50.0, tip=20.0):
    """A single-boom crane: capacity 50 t @ 3 m falling to 10 t @ 12 m (linear)."""
    cfg = BoomConfig(
        boom_length_m=15.0,
        max_tip_height_m=tip,
        points=[
            ChartPoint(3.0, max_cap),
            ChartPoint(12.0, max_cap * 0.2),
        ],
    )
    return CraneModel(
        manufacturer="Toy",
        model=name,
        type="Test",
        max_capacity_t=max_cap,
        max_boom_m=15.0,
        boom_configs=[cfg],
    )


# --- working radius -------------------------------------------------------

def test_horizontal_reach_pythagorean():
    assert horizontal_reach(3.0, 4.0) == pytest.approx(5.0)


def test_horizontal_reach_zero():
    assert horizontal_reach(0.0, 0.0) == 0.0


def test_working_radius_is_3d_slant():
    # working radius combines horizontal reach and vertical lift
    assert working_radius(4.0, 3.0) == pytest.approx(5.0)


def test_required_height_adds_headroom():
    req = LiftRequest(3, 4, vertical_lift_m=8.0, load_t=10.0, headroom_m=1.5)
    assert required_height(req) == pytest.approx(9.5)


# --- interpolation --------------------------------------------------------

def test_capacity_interpolates_midpoint():
    crane = _toy_crane()
    cap, boom = best_capacity(crane, radius_m=7.5, height_m=5.0)
    # Linear from (3, 50) to (12, 10): at 7.5 -> 50 + (4.5/9)*(10-50) = 50 - 20 = 30
    assert cap == pytest.approx(30.0)
    assert boom == 15.0


def test_capacity_at_endpoints():
    crane = _toy_crane()
    assert best_capacity(crane, 3.0, 5.0)[0] == pytest.approx(50.0)
    assert best_capacity(crane, 12.0, 5.0)[0] == pytest.approx(10.0)


def test_capacity_out_of_radius_range_returns_none():
    crane = _toy_crane()
    assert best_capacity(crane, 20.0, 5.0) == (None, None)


def test_capacity_height_too_high_returns_none():
    crane = _toy_crane(tip=20.0)
    # Require 25 m tip height; crane tops out at 20 m.
    assert best_capacity(crane, 7.5, 25.0) == (None, None)


# --- suitability / 90% boundary ------------------------------------------

def test_90pct_boundary_at_exactly_90_is_not_suitable():
    crane = _toy_crane()  # capacity at 7.5 m = 30 t
    load = 30.0 * SAFE_UTILIZATION  # exactly 90%
    req = LiftRequest(7.5, 0.0, vertical_lift_m=2.0, load_t=load, headroom_m=0.0)
    res = evaluate_crane(crane, req)
    assert res.utilization == pytest.approx(SAFE_UTILIZATION)
    assert res.suitable is False


def test_just_under_90pct_is_suitable():
    crane = _toy_crane()  # capacity at 7.5 m = 30 t
    load = 30.0 * 0.89
    req = LiftRequest(7.5, 0.0, vertical_lift_m=2.0, load_t=load, headroom_m=0.0)
    res = evaluate_crane(crane, req)
    assert res.suitable is True


def test_unreachable_crane_is_not_suitable():
    crane = _toy_crane()
    req = LiftRequest(50.0, 0.0, vertical_lift_m=2.0, load_t=5.0, headroom_m=0.0)
    res = evaluate_crane(crane, req)
    assert res.suitable is False
    assert res.capacity_t is None


# --- recommendation -------------------------------------------------------

def test_recommend_picks_smallest_suitable():
    small = _toy_crane("Small", max_cap=20.0)   # cap@7.5 = 12 t
    big = _toy_crane("Big", max_cap=100.0)       # cap@7.5 = 60 t
    req = LiftRequest(7.5, 0.0, vertical_lift_m=2.0, load_t=10.0, headroom_m=0.0)
    # Small: 10/12 = 83% suitable; Big: 10/60 = 17% suitable. Smallest suitable = Small.
    rec = recommend([big, small], req)
    assert rec is not None
    assert rec.crane.model == "Small"


def test_recommend_none_when_all_overloaded():
    small = _toy_crane("Small", max_cap=20.0)  # cap@7.5 = 12 t
    req = LiftRequest(7.5, 0.0, vertical_lift_m=2.0, load_t=100.0, headroom_m=0.0)
    assert recommend([small], req) is None


# --- real library ---------------------------------------------------------

def test_library_loads_and_is_sorted():
    cranes = load_library(DATA_DIR)
    assert len(cranes) >= 8
    caps = [c.max_capacity_t for c in cranes]
    assert caps == sorted(caps)


def test_library_charts_are_monotonic_decreasing():
    """Within each boom config, capacity should not increase with radius."""
    for crane in load_library(DATA_DIR):
        for cfg in crane.boom_configs:
            caps = [p.capacity_t for p in cfg.points]
            assert all(b <= a + 1e-9 for a, b in zip(caps, caps[1:])), (
                f"{crane.name} boom {cfg.boom_length_m} m not monotonic: {caps}"
            )


def test_library_realistic_lift_recommends_something():
    cranes = load_library(DATA_DIR)
    req = LiftRequest(5.0, 3.0, vertical_lift_m=8.0, load_t=40.0, headroom_m=1.5)
    assert horizontal_reach(5.0, 3.0) == pytest.approx(math.hypot(5.0, 3.0))
    rec = recommend(cranes, req)
    assert rec is not None
    assert rec.suitable
