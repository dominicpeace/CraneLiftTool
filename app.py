"""Crane Lifting Study Tool — Streamlit UI.

Run:
    streamlit run app.py
"""

from __future__ import annotations

import math

import pandas as pd
import streamlit as st

from crane_tool.data_loader import DEFAULT_DATA_DIR, CraneDataError, load_library
from crane_tool.chart_plot import geometry_sketch, plot_range_chart, plot_real_chart
from crane_tool.models import LiftRequest
from crane_tool.selector import (
    SAFE_UTILIZATION,
    evaluate_all,
    evaluate_crane,
    horizontal_reach,
    recommend,
    required_height,
    working_radius,
)

st.set_page_config(page_title="Crane Lifting Study", page_icon="🏗️", layout="wide")

DATA_ROOT = DEFAULT_DATA_DIR.parent  # .../data ; chart images live under data/charts/


@st.cache_data
def _load():
    return load_library()


def main() -> None:
    st.title("🏗️ Crane Lifting Study — quick check")
    st.caption(
        "Recommends a crane and shows the lift on its load chart. "
        "Indicative early-planning tool only."
    )

    st.warning(
        "**Indicative quick-check only.** Not a lift plan. Always verify the selected crane against "
        "the manufacturer's actual load chart for the correct counterweight / outrigger / boom "
        "configuration before lifting.",
        icon="⚠️",
    )

    try:
        full_library = _load()
    except CraneDataError as exc:
        st.error(f"Could not load crane library: {exc}")
        return

    # ---- Inputs ----
    with st.sidebar:
        st.header("Lift inputs")
        x = st.number_input("Horizontal X reach (m)", min_value=0.0, value=5.0, step=0.5)
        y = st.number_input("Horizontal Y reach (m)", min_value=0.0, value=3.0, step=0.5)
        lift = st.number_input("Vertical lift (m)", min_value=0.0, value=8.0, step=0.5)
        load = st.number_input("Total load incl. gear (t)", min_value=0.0, value=40.0, step=1.0)
        headroom = st.number_input(
            "Headroom allowance (m)",
            min_value=0.0,
            value=1.5,
            step=0.5,
            help="Added to vertical lift for hook-block / clearance to set the required tip height.",
        )
        st.divider()
        all_types = sorted({c.type for c in full_library})
        chosen_types = st.multiselect(
            "Crane types to consider",
            all_types,
            default=all_types,
            help="Filter the library, e.g. Rough Terrain vs All Terrain.",
        )
        caps = [c.max_capacity_t for c in full_library]
        cap_floor = float(math.floor(min(caps) / 10) * 10)
        cap_ceil = float(math.ceil(max(caps) / 10) * 10)
        cap_lo, cap_hi = st.slider(
            "Max rated capacity (t)",
            min_value=cap_floor,
            max_value=cap_ceil,
            value=(cap_floor, cap_ceil),
            step=5.0,
            help="Filter the library by each crane's headline maximum rated capacity.",
        )

    cranes = [
        c
        for c in full_library
        if c.type in chosen_types and cap_lo <= c.max_capacity_t <= cap_hi
    ]
    cap_filtered = bool(cranes)
    if not cap_filtered:
        cranes = full_library  # never leave the app with an empty library

    req = LiftRequest(
        x_reach_m=x, y_reach_m=y, vertical_lift_m=lift, load_t=load, headroom_m=headroom
    )
    reach = horizontal_reach(x, y)          # load-chart radius = sqrt(X^2 + Y^2)
    work_radius = working_radius(reach, lift)  # 3-D slant distance = sqrt(reach^2 + lift^2)
    height = required_height(req)

    # Geometry definitions sketch in the sidebar to avoid reach/radius confusion.
    with st.sidebar:
        st.divider()
        st.caption("Geometry")
        st.pyplot(geometry_sketch(x, y, lift), use_container_width=True)
        if cap_filtered:
            st.caption(f"Considering {len(cranes)} of {len(full_library)} cranes (filters applied).")
        else:
            st.caption(
                f"No crane matches the current type / capacity filter — showing all "
                f"{len(full_library)} instead."
            )

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Horizontal reach √(X²+Y²)", f"{reach:.2f} m")
    c2.metric("Vertical lift (Z)", f"{lift:.2f} m")
    c3.metric("Working radius √(reach²+lift²)", f"{work_radius:.2f} m")
    c4.metric("Load (incl. gear)", f"{load:.1f} t")

    # ---- First pass: all cranes, suitable ones first ----
    rec = recommend(cranes, req)
    results = evaluate_all(cranes, req)

    st.subheader("First pass — all cranes at this lift")
    if rec is None:
        st.error(
            "No crane in the library is suitable for this lift "
            f"(load must stay below {SAFE_UTILIZATION * 100:.0f}% of rated capacity). "
            "Consider a larger crane or revisit the lift geometry."
        )
    else:
        st.success(
            f"Recommended: **{rec.crane.name}** ({rec.crane.type}) — "
            f"{rec.capacity_t:.1f} t capacity, {rec.utilization_pct:.0f}% used, "
            f"boom ≈ {rec.boom_length_m:.0f} m.",
            icon="✅",
        )

    rows = []
    for r in results:
        rows.append(
            {
                "Crane": r.crane.name,
                "Type": r.crane.type,
                "Max capacity (t)": r.crane.max_capacity_t,
                "Capacity @ radius (t)": None if r.capacity_t is None else round(r.capacity_t, 1),
                "Utilization (%)": None
                if r.utilization_pct is None
                else round(r.utilization_pct, 0),
                "Boom used (m)": None if r.boom_length_m is None else round(r.boom_length_m, 0),
                "Verdict": (
                    "✅ Suitable"
                    if r.suitable
                    else "🚫 Out of reach"
                    if r.capacity_t is None
                    else "⛔ Not suitable"
                ),
                "_ok": r.suitable,
            }
        )
    # Suitable cranes first, then by max capacity.
    df = (
        pd.DataFrame(rows)
        .sort_values(["_ok", "Max capacity (t)"], ascending=[False, True])
        .drop(columns="_ok")
        .reset_index(drop=True)
    )
    st.dataframe(df, use_container_width=True, hide_index=True)

    # ---- Per-model load chart with crosshair lines ----
    st.divider()
    st.subheader("Load chart for a selected model")
    st.caption(
        "Pick a model to see its working-range chart. The red lines are your reach (vertical) and "
        "lift (horizontal); read the rated capacity where they meet a boom arc — same as checking "
        "the PDF chart by hand."
    )
    names = [c.name for c in cranes]
    by_name = {c.name: c for c in cranes}

    def _model_label(name: str) -> str:
        """Dropdown label: model + type + headline capacity + max boom, so the class and size of
        each crane is clear while choosing (not just the bare model name)."""
        c = by_name[name]
        return f"{name}  ·  {c.type}  ·  {c.max_capacity_t:.0f} t max  ·  boom {c.max_boom_m:.0f} m"

    default_name = rec.crane.name if rec is not None else names[-1]
    # Keep the user's chosen model sticky: default to the recommendation only on first load (or if
    # the current pick has been filtered out of the list), so changing the lift inputs to check
    # other duty points does NOT silently switch the chart to a different crane.
    if st.session_state.get("crane_model") not in names:
        st.session_state["crane_model"] = default_name
    chosen_name = st.selectbox("Crane model", names, key="crane_model", format_func=_model_label)
    if rec is not None and chosen_name != rec.crane.name:
        st.caption(f"🎯 Recommended for this lift: **{rec.crane.name}** (selection stays on your choice).")
    chosen = by_name[chosen_name]

    # Headline specs of the selected crane, so it is clear what class/size has been picked.
    s1, s2, s3 = st.columns(3)
    s1.metric("Crane type", chosen.type)
    s2.metric("Max rated capacity", f"{chosen.max_capacity_t:.0f} t")
    s3.metric("Max boom length", f"{chosen.max_boom_m:.0f} m")

    result = evaluate_crane(chosen, req)

    if result.suitable:
        st.success(result.reason, icon="✅")
    else:
        st.error(result.reason, icon="⛔")

    cal = chosen.wr_chart
    img = (DATA_ROOT / cal["image"]) if cal else None
    has_real = bool(cal and img is not None and img.exists())
    # The duty point can be drawn on the real chart only if it falls within the charted axes.
    on_chart = has_real and result.radius_m <= cal["r_max"] and req.vertical_lift_m <= cal["h_max"]

    if has_real and (result.capacity_t is not None or on_chart):
        st.pyplot(plot_real_chart(result, req, str(img)), use_container_width=True)
        if result.capacity_t is None:
            st.caption(
                "Duty point shown on the actual manufacturer working-range chart — it falls beyond "
                "the longest boom's reach, so there is no rated capacity here. Verify against the PDF."
            )
        else:
            st.caption(
                "Actual manufacturer working-range chart with your reach (vertical) and lift "
                "(horizontal) lines — read the rated capacity where they meet a boom arc."
            )
    elif result.capacity_t is not None:
        st.pyplot(plot_range_chart(result, req), use_container_width=False)
        st.caption("Reconstructed chart (no source diagram available for this model).")
    else:
        st.info(f"No chart point for this crane at the requested radius/height ({result.reason})")

    if chosen.data_status:
        st.caption(f"ℹ️ {chosen.name} data status: {chosen.data_status}")


if __name__ == "__main__":
    main()
