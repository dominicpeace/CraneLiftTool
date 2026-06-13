"""Crane Lifting Study Tool — Streamlit UI.

Run:
    streamlit run app.py
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from crane_tool.data_loader import CraneDataError, load_library
from crane_tool.chart_plot import plot_duty_point, plot_load_chart
from crane_tool.models import LiftRequest
from crane_tool.selector import (
    SAFE_UTILIZATION,
    evaluate_all,
    evaluate_crane,
    recommend,
    required_height,
    working_radius,
)

st.set_page_config(page_title="Crane Lifting Study", page_icon="🏗️", layout="wide")


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

    cranes = [c for c in full_library if c.type in chosen_types] or full_library
    st.caption(f"Considering **{len(cranes)}** crane(s) of {len(full_library)} in the library.")

    req = LiftRequest(
        x_reach_m=x, y_reach_m=y, vertical_lift_m=lift, load_t=load, headroom_m=headroom
    )
    radius = working_radius(x, y)
    height = required_height(req)

    c1, c2, c3 = st.columns(3)
    c1.metric("Working radius √(X²+Y²)", f"{radius:.2f} m")
    c2.metric("Required tip height", f"{height:.2f} m")
    c3.metric("Load (incl. gear)", f"{load:.1f} t")

    # ---- Recommendation ----
    rec = recommend(cranes, req)
    st.subheader("Recommended crane")
    if rec is None:
        st.error(
            "No crane in the library is suitable for this lift "
            f"(load must stay below {SAFE_UTILIZATION * 100:.0f}% of rated capacity). "
            "Consider a larger crane or revisit the lift geometry."
        )
    else:
        rc1, rc2, rc3 = st.columns([2, 1, 1])
        rc1.success(f"**{rec.crane.name}** — {rec.crane.type}")
        rc2.metric("Capacity at radius", f"{rec.capacity_t:.1f} t")
        rc3.metric("Utilization", f"{rec.utilization_pct:.0f} %")
        st.caption(f"{rec.reason}  Boom length used ≈ {rec.boom_length_m:.0f} m.")

    # ---- Model selection (override) ----
    st.subheader("Load chart")
    names = [c.name for c in cranes]
    default_name = rec.crane.name if rec is not None else names[-1]
    default_idx = names.index(default_name)
    chosen_name = st.selectbox(
        "Crane model (override the recommendation to compare)",
        names,
        index=default_idx,
    )
    chosen = next(c for c in cranes if c.name == chosen_name)
    result = evaluate_crane(chosen, req)

    if result.suitable:
        st.success(result.reason, icon="✅")
    else:
        st.error(result.reason, icon="⛔")

    if result.capacity_t is not None:
        plot_col, duty_col = st.columns(2)
        with plot_col:
            st.pyplot(plot_load_chart(result, req))
        with duty_col:
            st.pyplot(plot_duty_point(result, req))
    else:
        st.info(
            "No load-chart curve to plot for this crane at the requested radius/height "
            f"({result.reason})"
        )
        if chosen.data_status:
            st.caption(f"Data status: {chosen.data_status}")

    if chosen.data_status:
        st.caption(f"ℹ️ {chosen.name} data status: {chosen.data_status}")

    # ---- Comparison table ----
    st.subheader("All cranes at this lift")
    rows = []
    for r in evaluate_all(cranes, req):
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
                "Verdict": "✅ Suitable" if r.suitable else "⛔ Not suitable",
            }
        )
    df = pd.DataFrame(rows).sort_values("Max capacity (t)").reset_index(drop=True)
    st.dataframe(df, use_container_width=True, hide_index=True)


if __name__ == "__main__":
    main()
