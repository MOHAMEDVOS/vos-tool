import streamlit as st
import pandas as pd

from app_ai.auth.authentication import get_current_username, get_current_user_role
from lib.dashboard_manager import user_manager


def show_phrase_management_section():
    """Display the Phrase Management section for Owner users."""

    # Verify Owner access
    current_username = get_current_username("Unknown")
    current_user_role = get_current_user_role(user_manager) or user_manager.get_user_role(current_username)

    if current_user_role != "Owner":
        st.error("Access Denied: Phrase Management is only available to Owner users.")
        return

    # Import phrase learning manager
    try:
        from lib.phrase_learning import get_phrase_learning_manager

        learning_manager = get_phrase_learning_manager()
    except Exception as e:
        st.error(f"Failed to load phrase learning system: {e}")
        return

    # Get statistics
    stats = learning_manager.get_repository_stats()

    # Statistics cards
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.markdown(
            f"""
        <div style="
            background: linear-gradient(135deg, rgba(168,85,247,0.1) 0%, rgba(124,58,237,0.1) 100%);
            border: 2px solid rgba(168,85,247,0.3);
            border-radius: 12px;
            padding: 1.5rem;
            text-align: center;
            backdrop-filter: blur(10px);
        ">
            <h3 style="color: #a855f7; font-size: 2rem; margin: 0;">{stats['total_phrases']}</h3>
            <p style="color: #94a3b8; margin: 0.5rem 0 0 0;">Total Phrases</p>
        </div>
        """,
            unsafe_allow_html=True,
        )

    with col2:
        st.markdown(
            f"""
        <div style="
            background: linear-gradient(135deg, rgba(34,197,94,0.1) 0%, rgba(22,163,74,0.1) 100%);
            border: 2px solid rgba(34,197,94,0.3);
            border-radius: 12px;
            padding: 1.5rem;
            text-align: center;
            backdrop-filter: blur(10px);
        ">
            <h3 style="color: #22c55e; font-size: 2rem; margin: 0;">{stats['pending_count']}</h3>
            <p style="color: #94a3b8; margin: 0.5rem 0 0 0;">Pending Review</p>
        </div>
        """,
            unsafe_allow_html=True,
        )

    with col3:
        st.markdown(
            f"""
        <div style="
            background: linear-gradient(135deg, rgba(59,130,246,0.1) 0%, rgba(37,99,235,0.1) 100%);
            border: 2px solid rgba(59,130,246,0.3);
            border-radius: 12px;
            padding: 1.5rem;
            text-align: center;
            backdrop-filter: blur(10px);
        ">
            <h3 style="color: #3b82f6; font-size: 2rem; margin: 0;">{stats['auto_learned_count']}</h3>
            <p style="color: #94a3b8; margin: 0.5rem 0 0 0;">Auto-Learned</p>
        </div>
        """,
            unsafe_allow_html=True,
        )

    with col4:
        st.markdown(
            f"""
        <div style="
            background: linear-gradient(135deg, rgba(245,158,11,0.1) 0%, rgba(217,119,6,0.1) 100%);
            border: 2px solid rgba(245,158,11,0.3);
            border-radius: 12px;
            padding: 1.5rem;
            text-align: center;
            backdrop-filter: blur(10px);
        ">
            <h3 style="color: #f59e0b; font-size: 2rem; margin: 0;">{stats['categories']}</h3>
            <p style="color: #94a3b8; margin: 0.5rem 0 0 0;">Categories</p>
        </div>
        """,
            unsafe_allow_html=True,
        )

    st.markdown("<br>", unsafe_allow_html=True)

    st.markdown("---")
    
    # Tab interface
    tab1, tab2, tab3 = st.tabs(["Pending Review", "Repository", "Settings"])

    with tab1:
        show_pending_phrases_tab(learning_manager)

    with tab2:
        show_repository_tab(learning_manager)

    with tab3:
        show_learning_settings_tab(learning_manager)


def show_pending_phrases_tab(learning_manager):
    """Show pending phrases for review."""

    st.subheader("Phrases Pending Review")

    pending_phrases = learning_manager.get_pending_phrases()

    if not pending_phrases:
        st.info("No phrases pending review.")
        return

    # Group by priority
    high_priority = [p for p in pending_phrases if p["confidence"] >= 0.90]
    medium_priority = [p for p in pending_phrases if 0.80 <= p["confidence"] < 0.90]
    low_priority = [p for p in pending_phrases if p["confidence"] < 0.80]

    if high_priority:
        st.markdown("### High Priority (Confidence ≥ 90%)")
        for phrase in high_priority:
            show_phrase_card(phrase, learning_manager, priority="high")

    if medium_priority:
        st.markdown("### Medium Priority (Confidence 80-89%)")
        for phrase in medium_priority:
            show_phrase_card(phrase, learning_manager, priority="medium")

    if low_priority:
        st.markdown("### Low Priority (Confidence < 80%)")
        for phrase in low_priority:
            show_phrase_card(phrase, learning_manager, priority="low")


def show_phrase_card(phrase, learning_manager, priority: str = "medium"):
    """Display a phrase card with approve/reject options."""

    # Color scheme based on priority
    if priority == "high":
        border_color = "#ef4444"
        bg_color = "rgba(239,68,68,0.1)"
    elif priority == "medium":
        border_color = "#f59e0b"
        bg_color = "rgba(245,158,11,0.1)"
    else:
        border_color = "#3b82f6"
        bg_color = "rgba(59,130,246,0.1)"

    with st.container():
        st.markdown(
            f"""
        <div style="
            border: 2px solid {border_color};
            border-radius: 12px;
            padding: 1.5rem;
            margin: 1rem 0;
            background: {bg_color};
            backdrop-filter: blur(10px);
        ">
            <div style="display: flex; justify-content: space-between; align-items: start; margin-bottom: 1rem;">
                <div>
                    <h4 style="color: {border_color}; margin: 0 0 0.5rem 0; font-size: 1.2rem;">
                        "{phrase['phrase']}"
                    </h4>
                    <p style="color: #94a3b8; margin: 0; font-size: 0.9rem;">
                        Category: {phrase['category']} |
                        Confidence: {phrase['confidence']:.1%} |
                        Detected: {phrase['detection_count']} times
                    </p>
                </div>
            </div>
            <div style="margin: 1rem 0;">
                <p style="color: #e2e8f0; margin: 0; font-size: 0.9rem;">
                    <strong>Similar to:</strong> {phrase['similar_to']}
                </p>
                <p style="color: #e2e8f0; margin: 0.5rem 0 0 0; font-size: 0.9rem;">
                    <strong>Context:</strong> {phrase['sample_contexts'][:100]}...
                </p>
            </div>
        </div>
        """,
            unsafe_allow_html=True,
        )

        # Action buttons
        col1, col2, col3 = st.columns([1, 1, 4])

        with col1:
            if st.button("Approve", key=f"approve_{phrase['id']}", type="primary"):
                if learning_manager.approve_phrase(phrase["id"]):
                    st.success(f"Approved: '{phrase['phrase']}'")
                    st.rerun()
                else:
                    st.error("Failed to approve phrase")

        with col2:
            if st.button("Reject", key=f"reject_{phrase['id']}"):
                if learning_manager.reject_phrase(phrase["id"], "Manual rejection"):
                    st.success(f"Rejected: '{phrase['phrase']}'")
                    st.rerun()
                else:
                    st.error("Failed to reject phrase")


def show_repository_tab(learning_manager):
    """Show repository management."""

    st.subheader("Repository Management")

    # Manual phrase addition section
    st.markdown("### Add New Phrase Manually")

    with st.expander("Add Phrase", expanded=False):
        col1, col2 = st.columns([3, 1])

        with col1:
            new_phrase = st.text_input(
                "Enter new phrase",
                placeholder="e.g., do you have any other properties to sell",
                help="Enter the rebuttal phrase you want to add",
            )

        with col2:
            # Get existing categories for dropdown
            repository = learning_manager.get_repository_phrases()
            existing_categories = list(repository.keys()) if repository else []

            category_options = existing_categories + ["Create New Category"]
            selected_category = st.selectbox(
                "Category",
                options=category_options,
                help="Select existing category or create new one",
            )

        # If creating new category, show text input
        if selected_category == "Create New Category":
            new_category = st.text_input(
                "New Category Name",
                placeholder="e.g., CUSTOM_REBUTTAL_FAMILY",
                help="Use UPPERCASE with underscores (e.g., MY_CUSTOM_FAMILY)",
            )
            final_category = new_category
        else:
            final_category = selected_category

        # Add phrase button
        col_add, col_info = st.columns([1, 3])

        with col_add:
            if st.button("Add Phrase", type="primary", disabled=not new_phrase or not final_category):
                result = learning_manager.add_phrase_manually(new_phrase, final_category)

                if result["success"]:
                    st.success(result["message"])
                    st.rerun()  # Refresh to show new phrase
                else:
                    st.error(result["message"])

        with col_info:
            if new_phrase and final_category:
                st.info(f"Will add: '{new_phrase}' → {final_category}")

    # Bulk phrase addition section
    st.markdown("### Add Multiple Phrases")

    with st.expander("Bulk Add Phrases", expanded=False):
        bulk_category = st.selectbox(
            "Select Category for Bulk Add",
            options=existing_categories + ["Create New Category"],
            key="bulk_category",
            help="All phrases will be added to this category",
        )

        if bulk_category == "Create New Category":
            bulk_new_category = st.text_input(
                "New Category Name for Bulk Add",
                placeholder="e.g., BULK_ADDED_FAMILY",
                key="bulk_new_category",
            )
            bulk_final_category = bulk_new_category
        else:
            bulk_final_category = bulk_category

        bulk_phrases = st.text_area(
            "Enter phrases (one per line)",
            placeholder=(
                "do you have any other properties\n"
                "any other houses you want to sell\n"
                "do you own any other real estate"
            ),
            height=150,
            help="Enter each phrase on a separate line",
        )

        if st.button(
            "Add All Phrases",
            type="secondary",
            disabled=not bulk_phrases or not bulk_final_category,
        ):
            if bulk_phrases and bulk_final_category:
                phrases_list = [p.strip() for p in bulk_phrases.split("\n") if p.strip()]

                success_count = 0
                error_count = 0
                errors: list[str] = []

                for phrase in phrases_list:
                    result = learning_manager.add_phrase_manually(phrase, bulk_final_category)
                    if result["success"]:
                        success_count += 1
                    else:
                        error_count += 1
                        errors.append(f"'{phrase}': {result['message']}")

                if success_count > 0:
                    st.success(f"Successfully added {success_count} phrases to {bulk_final_category}")

                if error_count > 0:
                    st.warning(f"Failed to add {error_count} phrases:")
                    for error in errors[:5]:  # Show first 5 errors
                        st.text(f"  • {error}")
                    if len(errors) > 5:
                        st.text(f"  ... and {len(errors) - 5} more errors")

                if success_count > 0:
                    st.rerun()  # Refresh to show new phrases

    st.markdown("---")

    # Repository display section
    repository = learning_manager.get_repository_phrases()

    if not repository:
        st.info(
            "No phrases in repository. Use the 'Rebuild Repository' button in Settings "
            "to import existing phrases."
        )
        return

    # Create a comprehensive table of all phrases
    all_phrases_data: list[dict] = []
    for category, phrases in repository.items():
        for phrase in phrases:
            all_phrases_data.append(
                {
                    "ID": len(all_phrases_data) + 1,
                    "Category": category,
                    "Phrase": phrase,
                    "Length": len(phrase.split()),
                    "Characters": len(phrase),
                }
            )

    if not all_phrases_data:
        st.info("No phrases found in repository.")
        return

    # Convert to DataFrame for better display
    df = pd.DataFrame(all_phrases_data)

    # Add search functionality
    col1, col2 = st.columns([3, 1])
    with col1:
        search_term = st.text_input(
            "Search phrases",
            placeholder="Enter search term...",
            key="repository_search_term",
        )
    with col2:
        category_filter = st.selectbox(
            "Filter by Category",
            options=["All Categories"] + list(repository.keys()),
            key="repository_category_filter",
        )

    # Apply filters
    filtered_df = df.copy()

    if search_term:
        filtered_df = filtered_df[
            filtered_df["Phrase"].str.contains(search_term, case=False, na=False)
        ]

    if category_filter != "All Categories":
        filtered_df = filtered_df[filtered_df["Category"] == category_filter]

    # Display summary
    st.markdown(
        f"""
    <div style="
        background: linear-gradient(135deg, rgba(59,130,246,0.1) 0%, rgba(37,99,235,0.1) 100%);
        border: 2px solid rgba(59,130,246,0.3);
        border-radius: 12px;
        padding: 1rem;
        margin: 1rem 0;
        text-align: center;
    ">
        <p style="color: #3b82f6; margin: 0; font-weight: 600;">
            Showing {len(filtered_df)} of {len(df)} phrases across {len(repository)} categories
        </p>
    </div>
    """,
        unsafe_allow_html=True,
    )

    # Display the table with modern styling
    if len(filtered_df) > 0:
        # Add custom CSS for left alignment
        st.markdown(
            """
        <style>
        /* Force left alignment for all dataframe content */
        [data-testid="stDataFrame"] td,
        [data-testid="stDataFrame"] th,
        [data-testid="stDataFrame"] .col_heading,
        [data-testid="stDataFrame"] .data-cell,
        [data-testid="stDataFrame"] div,
        [data-testid="stDataFrame"] span {
            text-align: left !important;
            justify-content: flex-start !important;
        }

        /* Target specific column types */
        [data-testid="stDataFrame"] [data-column-type="number"],
        [data-testid="stDataFrame"] [data-column-type="integer"] {
            text-align: left !important;
        }

        /* Additional selectors for stubborn elements */
        .stDataFrame * {
            text-align: left !important;
        }
        </style>
        """,
            unsafe_allow_html=True,
        )

        # Configure column display
        st.dataframe(
            filtered_df,
            width="stretch",
            hide_index=True,
            column_config={
                "ID": st.column_config.NumberColumn("ID", width="small"),
                "Category": st.column_config.TextColumn("Category", width="medium"),
                "Phrase": st.column_config.TextColumn("Phrase", width="large"),
                "Length": st.column_config.NumberColumn("Words", width="small"),
                "Characters": st.column_config.NumberColumn("Chars", width="small"),
            },
            column_order=["ID", "Category", "Phrase", "Length", "Characters"],
            height=600,  # Fixed height with scrolling
        )

        # Category breakdown
        st.markdown("### Category Breakdown")
        category_counts = filtered_df["Category"].value_counts()

        # Display category stats in columns
        cols = st.columns(min(4, len(category_counts)))
        for i, (category, count) in enumerate(category_counts.items()):
            with cols[i % len(cols)]:
                percentage = (count / len(filtered_df)) * 100
                st.markdown(
                    f"""
                <div style="
                    background: linear-gradient(135deg, rgba(168,85,247,0.1) 0%, rgba(124,58,237,0.1) 100%);
                    border: 2px solid rgba(168,85,247,0.3);
                    border-radius: 8px;
                    padding: 0.75rem;
                    text-align: center;
                    margin: 0.25rem 0;
                ">
                    <h4 style="color: #a855f7; margin: 0; font-size: 1.1rem;">{count}</h4>
                    <p style="color: #94a3b8; margin: 0.25rem 0 0 0; font-size: 0.8rem; font-weight: 600;">
                        {category.replace('_', ' ').title()}
                    </p>
                    <p style="color: #64748b; margin: 0; font-size: 0.7rem;">
                        {percentage:.1f}%
                    </p>
                </div>
                """,
                    unsafe_allow_html=True,
                )
    else:
        st.warning("No phrases match your search criteria.")


def show_analytics_tab(learning_manager):
    """Show comprehensive learning analytics dashboard."""

    st.subheader("Phrase Management Analytics")

    # Get analytics data
    try:
        # Repository statistics
        repository_phrases = learning_manager.get_repository_phrases()
        pending_phrases = learning_manager.get_pending_phrases()

        # Create metrics columns
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            total_phrases = sum(len(phrases) for phrases in repository_phrases.values())
            st.metric("Total Repository Phrases", total_phrases)

        with col2:
            pending_count = len(pending_phrases)
            st.metric("Pending Review", pending_count)

        with col3:
            category_count = len(repository_phrases)
            st.metric("Active Categories", category_count)

        with col4:
            if pending_phrases:
                avg_confidence = sum(p["confidence"] for p in pending_phrases) / len(pending_phrases)
                st.metric("Avg Pending Confidence", f"{avg_confidence:.3f}")
            else:
                st.metric("Avg Pending Confidence", "N/A")

        # Repository breakdown chart
        st.markdown("### Repository Distribution by Category")
        if repository_phrases:
            # Create category data
            category_data: list[dict] = []
            for category, phrases in repository_phrases.items():
                category_data.append(
                    {
                        "Category": category.replace("_FAMILY", "").replace("_", " ").title(),
                        "Phrase Count": len(phrases),
                        "Percentage": (len(phrases) / total_phrases) * 100,
                    }
                )

            df_categories = pd.DataFrame(category_data)
            df_categories = df_categories.sort_values("Phrase Count", ascending=False)

            # Display as chart
            col1, col2 = st.columns([2, 1])

            with col1:
                st.bar_chart(df_categories.set_index("Category")["Phrase Count"])

            with col2:
                st.dataframe(
                    df_categories,
                    hide_index=True,
                    column_config={
                        "Category": st.column_config.TextColumn("Category", width="large"),
                        "Phrase Count": st.column_config.NumberColumn("Count", width="small"),
                        "Percentage": st.column_config.NumberColumn(
                            "Percentage", format="%.1f%%", width="small"
                        ),
                    },
                )

        # Pending phrases analysis
        if pending_phrases:
            st.markdown("### Pending Phrases Analysis")

            # Confidence distribution
            col1, col2 = st.columns(2)

            with col1:
                st.markdown("#### Confidence Score Distribution")
                confidence_ranges = {
                    "Very High (0.95+)": len([p for p in pending_phrases if p["confidence"] >= 0.95]),
                    "High (0.90-0.94)": len(
                        [p for p in pending_phrases if 0.90 <= p["confidence"] < 0.95]
                    ),
                    "Good (0.85-0.89)": len(
                        [p for p in pending_phrases if 0.85 <= p["confidence"] < 0.90]
                    ),
                    "Moderate (0.80-0.84)": len(
                        [p for p in pending_phrases if 0.80 <= p["confidence"] < 0.85]
                    ),
                    "Low (<0.80)": len([p for p in pending_phrases if p["confidence"] < 0.80]),
                }

                confidence_df = pd.DataFrame(
                    list(confidence_ranges.items()), columns=["Confidence Range", "Count"]
                )
                confidence_df = confidence_df[confidence_df["Count"] > 0]

                if not confidence_df.empty:
                    st.bar_chart(confidence_df.set_index("Confidence Range")["Count"])
                else:
                    st.info("No pending phrases to analyze")

            with col2:
                st.markdown("#### Category Distribution (Pending)")
                pending_categories: dict[str, int] = {}
                for phrase in pending_phrases:
                    cat = phrase["category"].replace("_FAMILY", "").replace("_", " ").title()
                    pending_categories[cat] = pending_categories.get(cat, 0) + 1

                if pending_categories:
                    pending_cat_df = pd.DataFrame(
                        list(pending_categories.items()), columns=["Category", "Count"]
                    )
                    st.bar_chart(pending_cat_df.set_index("Category")["Count"])

            # Recent high-confidence phrases
            st.markdown("#### Recent High-Confidence Phrases")
            high_conf_phrases = [p for p in pending_phrases if p["confidence"] >= 0.90]
            high_conf_phrases.sort(key=lambda x: x["confidence"], reverse=True)

            if high_conf_phrases:
                for i, phrase in enumerate(high_conf_phrases[:5], 1):
                    with st.expander(
                        f"{i}. {phrase['phrase']} (Confidence: {phrase['confidence']:.3f})"
                    ):
                        st.write(f"**Category:** {phrase['category']}")
                        st.write(f"**Confidence:** {phrase['confidence']:.3f}")
                        if phrase.get("sample_contexts"):
                            st.write(f"**Context:** {phrase['sample_contexts'][:200]}...")
            else:
                st.info("No high-confidence phrases pending review")

        # Learning system performance
        st.markdown("### Learning System Performance")

        col1, col2 = st.columns(2)

        with col1:
            st.markdown("#### Repository Growth")
            # Show phrase count by category with growth indicators
            growth_data: list[dict] = []
            for category, phrases in repository_phrases.items():
                growth_data.append(
                    {
                        "Category": category.replace("_FAMILY", "").replace("_", " ").title(),
                        "Current Count": len(phrases),
                        "Status": "Active" if len(phrases) > 0 else "Empty",
                    }
                )

            growth_df = pd.DataFrame(growth_data)
            growth_df = growth_df.sort_values("Current Count", ascending=False)

            st.dataframe(
                growth_df,
                hide_index=True,
                column_config={
                    "Category": st.column_config.TextColumn("Category", width="large"),
                    "Current Count": st.column_config.NumberColumn("Phrases", width="small"),
                    "Status": st.column_config.TextColumn("Status", width="small"),
                },
            )

        with col2:
            st.markdown("#### Quality Metrics")

            # Calculate quality metrics
            if pending_phrases:
                high_quality = len([p for p in pending_phrases if p["confidence"] >= 0.90])
                medium_quality = len(
                    [p for p in pending_phrases if 0.80 <= p["confidence"] < 0.90]
                )
                low_quality = len([p for p in pending_phrases if p["confidence"] < 0.80])

                quality_metrics = {
                    "High Quality (≥0.90)": high_quality,
                    "Medium Quality (0.80-0.89)": medium_quality,
                    "Low Quality (<0.80)": low_quality,
                }

                for metric, count in quality_metrics.items():
                    percentage = (count / len(pending_phrases)) * 100 if pending_phrases else 0
                    st.metric(metric, f"{count} ({percentage:.1f}%)")
            else:
                st.info("No pending phrases for quality analysis")

        # System configuration
        st.markdown("### System Configuration")
        col1, col2, col3 = st.columns(3)

        with col1:
            st.metric("Confidence Threshold", f"{learning_manager.confidence_threshold:.2f}")

        with col2:
            st.metric("Frequency Threshold", learning_manager.frequency_threshold)

        with col3:
            st.metric("Auto-Approve Threshold", f"{learning_manager.auto_approve_threshold:.2f}")

        # Phrase length analysis
        st.markdown("### Phrase Length Analysis")
        col1, col2 = st.columns(2)

        with col1:
            st.markdown("#### Word Count Distribution")
            # Analyze phrase lengths across repository
            length_data: dict[str, int] = {}
            for category, phrases in repository_phrases.items():
                for phrase in phrases:
                    word_count = len(phrase.split())
                    length_range = f"{(word_count // 5) * 5}-{(word_count // 5) * 5 + 4} words"
                    length_data[length_range] = length_data.get(length_range, 0) + 1

            if length_data:
                length_df = pd.DataFrame(
                    list(length_data.items()), columns=["Length Range", "Count"]
                )
                length_df = length_df.sort_values("Length Range")
                st.bar_chart(length_df.set_index("Length Range")["Count"])

        with col2:
            st.markdown("#### Category Efficiency")
            # Show average phrase length per category
            category_efficiency: list[dict] = []
            for category, phrases in repository_phrases.items():
                if phrases:
                    avg_length = sum(len(phrase.split()) for phrase in phrases) / len(phrases)
                    category_efficiency.append(
                        {
                            "Category": category.replace("_FAMILY", "").replace("_", " ").title(),
                            "Avg Words": round(avg_length, 1),
                        }
                    )

            if category_efficiency:
                efficiency_df = pd.DataFrame(category_efficiency)
                st.dataframe(
                    efficiency_df,
                    hide_index=True,
                    column_config={
                        "Category": st.column_config.TextColumn("Category", width="large"),
                        "Avg Words": st.column_config.NumberColumn("Avg Words", width="small"),
                    },
                )

    except Exception as e:
        st.error(f"Error loading analytics data: {e}")
        st.info("Please ensure the phrase learning system is properly initialized.")


def show_learning_settings_tab(learning_manager):
    """Show learning system settings."""

    st.subheader("Learning Settings")

    col1, col2 = st.columns(2)

    with col1:
        confidence_input = st.text_input(
            "Minimum Confidence Threshold (0.50 - 1.00)",
            value=f"{learning_manager.confidence_threshold:.2f}",
            help=(
                "Minimum confidence required to track semantic matches; type an exact value "
                "between 0.50 and 1.00"
            ),
        )
        try:
            confidence_threshold = float(confidence_input)
        except ValueError:
            st.warning("Invalid confidence threshold; using the current setting.")
            confidence_threshold = learning_manager.confidence_threshold
        else:
            confidence_threshold = max(0.5, min(confidence_threshold, 1.0))

        frequency_threshold = st.number_input(
            "Frequency Threshold",
            min_value=1,
            max_value=20,
            value=learning_manager.frequency_threshold,
            help="Minimum detections before considering for auto-approval",
        )

    with col2:
        auto_approve_input = st.text_input(
            "Auto-Approve Threshold (0.80 - 1.00)",
            value=f"{learning_manager.auto_approve_threshold:.2f}",
            help=(
                "Confidence threshold for automatic approval; enter a value between 0.80 and 1.00 "
                "for higher precision"
            ),
        )
        try:
            auto_approve_threshold = float(auto_approve_input)
        except ValueError:
            st.warning("Invalid auto-approve threshold provided; using the current setting.")
            auto_approve_threshold = learning_manager.auto_approve_threshold
        else:
            auto_approve_threshold = max(0.8, min(auto_approve_threshold, 1.0))

    col_update, col_rebuild = st.columns(2)

    with col_update:
        if st.button("Update Settings", type="primary"):
            learning_manager.update_settings(
                confidence_threshold=confidence_threshold,
                frequency_threshold=frequency_threshold,
                auto_approve_threshold=auto_approve_threshold,
            )
            st.success("Settings updated successfully!")

    with col_rebuild:
        if st.button(
            "Rebuild Repository",
            help="Import all phrases from existing rebuttal detection system",
        ):
            with st.spinner("Rebuilding repository from existing phrases..."):
                if learning_manager.rebuild_repository_from_existing():
                    # Clear any search/filter state that might hide phrases
                    if "repository_search_term" in st.session_state:
                        del st.session_state["repository_search_term"]
                    if "repository_category_filter" in st.session_state:
                        del st.session_state["repository_category_filter"]
                    st.success(
                        "Repository rebuilt successfully! All existing phrases imported."
                    )
                    st.rerun()
                else:
                    st.error("Failed to rebuild repository.")

