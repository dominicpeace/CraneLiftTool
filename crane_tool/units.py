"""Unit conversions.

Source crane load charts are published in imperial units (US short tons, feet). The application
works internally in metric (metres, tonnes), so ingest tooling converts on the way in. These
helpers keep the conversion factors in one place.
"""

# 1 foot = 0.3048 metres (exact).
FEET_PER_METRE = 1.0 / 0.3048
METRES_PER_FOOT = 0.3048

# 1 US short ton = 2000 lb = 907.18474 kg = 0.90718474 metric tonnes (exact-ish).
TONNES_PER_SHORT_TON = 0.90718474
SHORT_TONS_PER_TONNE = 1.0 / TONNES_PER_SHORT_TON

# 1 lb = 0.45359237 kg -> tonnes
TONNES_PER_POUND = 0.45359237 / 1000.0


def ft_to_m(feet: float) -> float:
    """Convert feet to metres."""
    return feet * METRES_PER_FOOT


def m_to_ft(metres: float) -> float:
    """Convert metres to feet."""
    return metres * FEET_PER_METRE


def short_tons_to_tonnes(short_tons: float) -> float:
    """Convert US short tons to metric tonnes."""
    return short_tons * TONNES_PER_SHORT_TON


def tonnes_to_short_tons(tonnes: float) -> float:
    """Convert metric tonnes to US short tons."""
    return tonnes * SHORT_TONS_PER_TONNE


def pounds_to_tonnes(pounds: float) -> float:
    """Convert pounds to metric tonnes (load charts often list capacity in lb)."""
    return pounds * TONNES_PER_POUND
