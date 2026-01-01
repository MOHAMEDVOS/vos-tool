import streamlit as st
import pandas as pd

from lib.dashboard_manager import dashboard_manager


def show_flagged_calls_section():
    """Display the flagged calls review section.

    Extracted from app.py; behavior is kept identical.
    """

    st.markdown(
        """
    <div class="modern-card">
        <div class="card-header">
            <div class="card-title">
                🔍 Flagged Calls Review
            </div>
            <div class="card-subtitle">
                Calls with quality issues needing attention (Late Hello, Releasing, or Missing Rebuttals)
            </div>
        </div>
    </div>
    """,
        unsafe_allow_html=True,
    )

    st.markdown("### Flagged Calls for Action")

    # Add refresh button at the top
    col1, col2 = st.columns([3, 1])
    with col1:
        st.write("")  # Empty space
    with col2:
        if st.button(
            "Refresh Data",
            help="Reload data from storage",
            key="actions_refresh",
        ):
            # Clear any cached data and force reload
            if "dashboard_cache_timestamp" in st.session_state:
                del st.session_state.dashboard_cache_timestamp
            st.rerun()

    # Get combined data from current user's audits
    df = dashboard_manager.get_combined_agent_audit_data(
        st.session_state.get("username")
    )
    filtered_df = df.copy()

    with st.expander("🎛️ Filters", expanded=False):
        detection_filter = st.multiselect(
            "Detections to show",
            ["Late Hello", "Releasing", "Missing Rebuttal"],
            default=["Late Hello", "Releasing", "Missing Rebuttal"],
        )

        agent_options = sorted(
            filtered_df.get("Agent Name", pd.Series(dtype=str)).dropna().unique()
        )
        selected_agents = st.multiselect(
            "Agents",
            agent_options,
            default=agent_options,
        )

        date_range = None
        if "Timestamp" in filtered_df.columns:
            filtered_df["_timestamp_dt"] = pd.to_datetime(
                filtered_df["Timestamp"], errors="coerce"
            )
            min_date = filtered_df["_timestamp_dt"].min()
            max_date = filtered_df["_timestamp_dt"].max()
            if pd.notnull(min_date) and pd.notnull(max_date):
                date_range = st.date_input(
                    "Date range",
                    value=(min_date.date(), max_date.date()),
                )

    if selected_agents:
        filtered_df = filtered_df[filtered_df["Agent Name"].isin(selected_agents)]

    if date_range and "Timestamp" in filtered_df.columns:
        start_date, end_date = date_range
        filtered_df = filtered_df[
            (filtered_df["_timestamp_dt"].dt.date >= start_date)
            & (filtered_df["_timestamp_dt"].dt.date <= end_date)
        ]

    if "_timestamp_dt" in filtered_df.columns:
        filtered_df = filtered_df.drop(columns="_timestamp_dt")

    df = filtered_df

    if df.empty:
        st.info(
            "No agent audit data available. Run Agent Audits or Upload & Analyze to see "
            "flagged calls here."
        )
        return

    # Apply filtering criteria for flagged calls needing action:
    # Show calls with AT LEAST ONE issue (Late Hello OR Releasing OR Missing Rebuttal)
    filtered_df = df[
        (df["Late Hello Detection"] == "Yes")
        | (df["Releasing Detection"] == "Yes")
        | (df["Rebuttal Detection"] == "No")
    ].copy()

    if "Late Hello" not in detection_filter:
        filtered_df = filtered_df[filtered_df["Late Hello Detection"] != "Yes"]
    if "Releasing" not in detection_filter:
        filtered_df = filtered_df[filtered_df["Releasing Detection"] != "Yes"]
    if "Missing Rebuttal" not in detection_filter:
        filtered_df = filtered_df[filtered_df["Rebuttal Detection"] != "No"]

    if filtered_df.empty:
        st.info("No flagged calls found. Calls with issues will appear here after running audits.")
        return

    # Display summary metrics
    col1, col2, col3 = st.columns(3)

    with col1:
        total_calls = len(filtered_df)
        st.metric("Flagged Calls", total_calls)

    with col2:
        if "Agent Name" in filtered_df.columns:
            unique_agents = filtered_df["Agent Name"].nunique()
            st.metric("Agents Involved", unique_agents)
        else:
            st.metric("Agents Involved", "N/A")

    with col3:
        if "Phone Number" in filtered_df.columns:
            unique_numbers = filtered_df["Phone Number"].nunique()
            st.metric("Unique Contacts", unique_numbers)
        else:
            st.metric("Unique Contacts", "N/A")

    # Enhanced data table with conditional styling
    st.markdown("#### Detailed Call Review")

    def highlight_critical_issues(row: pd.Series) -> list[str]:
        """Apply conditional styling for critical call issues."""

        styles: list[str] = []
        for col in row.index:
            base_style = (
                "background-color: #000000; color: #ffffff; "
                "border: 1px solid rgba(255,255,255,0.08);"
            )

            # Highlight critical combinations
            if col in [
                "Late Hello Detection",
                "Releasing Detection",
                "Rebuttal Detection",
            ]:
                if row[col] == "Yes":
                    styles.append(
                        f"{base_style} background-color: rgba(239, 68, 68, 0.2); "
                        "border-left: 3px solid #ef4444;"
                    )
                else:
                    styles.append(
                        f"{base_style} background-color: rgba(34, 197, 94, 0.1); "
                        "border-left: 3px solid #22c55e;"
                    )
            else:
                styles.append(base_style)

        return styles

    # Display the data table with conditional styling
    if "actions_filter" in st.session_state and st.session_state.actions_filter == "combined":
        if not filtered_df.empty:
            styled_df = filtered_df.style.apply(highlight_critical_issues, axis=1)
            st.dataframe(styled_df, width="stretch", height=400)
    else:
        if not filtered_df.empty:
            styled_df = filtered_df.style.apply(highlight_critical_issues, axis=1)
            st.dataframe(styled_df, width="stretch", height=400)

    # Issue breakdown visualization
    if len(filtered_df) > 0:
        st.markdown("#### Issue Analysis")

        late_hello_count = (filtered_df["Late Hello Detection"] == "Yes").sum()
        releasing_count = (filtered_df["Releasing Detection"] == "Yes").sum()
        rebuttal_count = (filtered_df["Rebuttal Detection"] == "No").sum()

        issues_data = pd.DataFrame(
            {
                "Issue Type": ["Late Hello", "Releasing", "Missing Rebuttal"],
                "Count": [late_hello_count, releasing_count, rebuttal_count],
            }
        )

        issues_data["Percentage of Flagged"] = (
            issues_data["Count"] / issues_data["Count"].sum() * 100
        ).round(1)
        issues_data = issues_data.sort_values("Count", ascending=False)

        col1, col2 = st.columns([2, 1])
        with col1:
            st.markdown("**Issue Distribution in Flagged Calls:**")
            for _, row in issues_data.iterrows():
                percentage = row["Percentage of Flagged"]
                count = int(row["Count"])
                issue = row["Issue Type"]

                if issue == "Late Hello":
                    color = "#ef4444"  # red
                elif issue == "Releasing":
                    color = "#f59e0b"  # amber
                else:
                    color = "#8b5cf6"  # violet

                st.markdown(
                    f"<div style='margin: 0.25rem 0; color: {color}; font-weight: 600;'>"
                    f"{issue}: {count} calls ({percentage:.1f}% of flagged)</div>",
                    unsafe_allow_html=True,
                )

        with col2:
            st.markdown("**Issue Breakdown Table:**")
            st.dataframe(issues_data, hide_index=True)
