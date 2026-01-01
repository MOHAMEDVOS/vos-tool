from datetime import date, timedelta
import logging

import pandas as pd
import streamlit as st

logger = logging.getLogger(__name__)


def show_campaign_audit_dashboard(dashboard_manager, generate_csv_data):
    """Display Campaign Audit Dashboard with persistent data and date filtering."""
    
    st.markdown("### Campaign Audit Dashboard")
    
    # Campaign selection
    available_campaigns = dashboard_manager.get_available_campaigns(st.session_state.get('username'))
    
    if not available_campaigns:
        st.warning("No campaign audit data available. Run a Campaign Audit first to see results here.")
        return
    
    selected_campaign = st.selectbox(
        "Select Campaign",
        options=available_campaigns,
        key="campaign_select"
    )
    
    # Date range filter
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input(
            "Call Start Date (filters by when calls were made)",
            value=date.today() - timedelta(days=90),
            key="campaign_start_date"
        )
    with col2:
        end_date = st.date_input(
            "Call End Date (filters by when calls were made)", 
            value=date.today(),
            key="campaign_end_date"
        )
    
    # Load Data button
    if st.button("Load Campaign Data", type="primary", key="load_campaign_data"):
        with st.spinner("Loading campaign data..."):
            # Load campaign data for the selected date range
            df = dashboard_manager.load_campaign_audit_data(
                selected_campaign, 
                start_date, 
                end_date, 
                st.session_state.get('username')
            )
            
            # Store in session state
            st.session_state.campaign_dashboard_data = df
            st.success(f"Loaded {len(df)} records for campaign '{selected_campaign}'")
    
    # Display results if data is loaded
    if "campaign_dashboard_data" in st.session_state:
        df = st.session_state.campaign_dashboard_data

        if df.empty:
            st.warning("No data found for the selected date range.")
            return

        # Apply Lite Audit filtering: only show flagged calls for Lite Audit,
        # keep Heavy Audit data unchanged.
        try:
            if "Audit Type" in df.columns:
                # Separate heavy and lite
                heavy_mask = df["Audit Type"] == "Heavy Audit"
                lite_mask = df["Audit Type"] == "Lite Audit"

                heavy_df = df[heavy_mask]
                lite_df = df[lite_mask]

                # For Lite Audit, only keep flagged calls where releasing or late hello
                # detections are "Yes". Prefer detection column names used by the
                # processing pipeline, with a fallback to simpler names if present.
                if not lite_df.empty:
                    if {"Releasing Detection", "Late Hello Detection"}.issubset(
                        lite_df.columns
                    ):
                        lite_df = lite_df[
                            (lite_df["Releasing Detection"] == "Yes")
                            | (lite_df["Late Hello Detection"] == "Yes")
                        ]
                    elif {"Releasing", "Late Hello"}.issubset(lite_df.columns):
                        lite_df = lite_df[
                            (lite_df["Releasing"] == "Yes")
                            | (lite_df["Late Hello"] == "Yes")
                        ]

                # Combine back (Heavy unchanged, Lite filtered)
                df = pd.concat([heavy_df, lite_df], ignore_index=True)
        except Exception:
            # Fail gracefully: if anything goes wrong, show unfiltered data
            pass
        
        # Get metrics using the existing audit metrics function
        metrics = dashboard_manager.get_audit_metrics(df)
        
        # Display summary statistics
        col1, col2, col3, col4, col5 = st.columns(5)
        with col1:
            st.metric("Total Calls", metrics['total_calls'])
        with col2:
            st.metric("Flagged Calls", metrics['flagged_calls'])
        with col3:
            st.metric("Releasing Calls", metrics['releasing_calls'])
        with col4:
            st.metric("Late Hello Calls", metrics['late_hello_calls'])
        with col5:
            st.metric("Missing Rebuttals", metrics['rebuttal_calls'])
        
        # Date range info
        
        if 'Agent Name' in df.columns:
            df = df.sort_values('Agent Name', ascending=True, key=lambda col: col.str.lower()).reset_index(drop=True)

        # Remove unwanted columns from display (keep in data for CSV export)
        columns_to_hide = ['File Name', 'File Path', 'Call Duration', 'Confidence Score', 'audit_timestamp']
        display_df = df.copy()
        for col in columns_to_hide:
            if col in display_df.columns:
                display_df = display_df.drop(columns=[col])
        
        # Rename 'username' to 'Auditor' for display if it exists
        if 'username' in display_df.columns:
            display_df = display_df.rename(columns={'username': 'Auditor'})
        
        # Rename 'audit_type' to 'Audit Type' if it exists
        if 'audit_type' in display_df.columns:
            display_df = display_df.rename(columns={'audit_type': 'Audit Type'})
        
        # Standard column order (matching the image)
        standard_column_order = [
            'Agent Name',
            'Phone Number',
            'Timestamp',
            'Disposition',
            'Releasing Detection',
            'Late Hello Detection',
            'Rebuttal Detection',
            'Transcription',
            'Owner Name',
            'Agent Intro',
            'Reason for calling',
            'Intro Score',
            'Status',
            'Dialer Name',
            'Audit Type',
            'Auditor'
        ]
        
        # Handle column name variations - check all possible variations
        column_name_mapping = {}
        
        # Check for "Reason for calling" variations
        if 'Reason for Calling' in display_df.columns:
            column_name_mapping['Reason for Calling'] = 'Reason for calling'
        elif 'Reason for calling' not in display_df.columns:
            # Check for other possible variations
            for col in display_df.columns:
                if 'reason' in col.lower() and 'calling' in col.lower():
                    column_name_mapping[col] = 'Reason for calling'
                    break
        
        # Check for "Dialer Name" variations
        if 'dialer_name' in display_df.columns:
            column_name_mapping['dialer_name'] = 'Dialer Name'
        elif 'Dialer Name' not in display_df.columns:
            # Check for other possible variations
            for col in display_df.columns:
                if 'dialer' in col.lower():
                    column_name_mapping[col] = 'Dialer Name'
                    break
        
        # Apply column name mappings
        if column_name_mapping:
            display_df = display_df.rename(columns=column_name_mapping)
        
        # Add missing columns with default values
        for col in standard_column_order:
            if col not in display_df.columns:
                if col in ['Rebuttal Detection', 'Transcription', 'Agent Intro', 'Owner Name', 'Intro Score', 'Status', 'Audit Type']:
                    display_df[col] = 'N/A'
                else:
                    display_df[col] = ''
        
        # Reorder columns to match standard order
        existing_standard_cols = [col for col in standard_column_order if col in display_df.columns]
        remaining_cols = [col for col in display_df.columns if col not in standard_column_order]
        
        # Final column order: standard columns first, then any remaining columns
        display_df = display_df[existing_standard_cols + remaining_cols]

        # Display the data table (after any Lite/Heavy filtering)
        st.dataframe(display_df, width="stretch")

        # Download options - CSV only (respecting same filtering)
        # Use display_df for CSV to include the renamed 'Auditor' column
        csv_data, filename = generate_csv_data(
            display_df, f"campaign_audit_{selected_campaign}"
        )
        st.download_button(
            label="Download CSV",
            data=csv_data,
            file_name=filename,
            mime="text/csv",
            key="campaign_csv_download"
        )

        # Generate Performance Report section
        with st.expander("Performance Report", expanded=False):
            
            col1, col2 = st.columns([2, 1])
            with col1:
                if st.button("Generate Performance Report", type="primary"):
                    with st.spinner("Analyzing audit data and generating insights..."):
                        try:
                            report = dashboard_manager.generate_performance_report(df, st.session_state.get('username'))
                            st.session_state.performance_report = report
                            st.success("Performance report generated successfully!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error generating report: {str(e)}")
            
            with col2:
                if 'performance_report' in st.session_state:
                    if st.button("Clear Report", help="Remove the current report"):
                        del st.session_state.performance_report
                        st.rerun()
            
            # Display the report if it exists
            if 'performance_report' in st.session_state:
                report = st.session_state.performance_report
                
                if 'error' in report:
                    if report['error'] == 'No audit data available for analysis':
                        st.info("No audit data available yet. Run some agent audits to generate performance insights.")
                    else:
                        st.error(f"Report Error: {report['error']}")
                    return  # Exit early - don't try to access other report keys

                # Campaign Performance Report table-style UI using Streamlit dataframe
                st.markdown("#### Campaign Performance Report")

                issue_table = report.get('issue_table', {})

                audit_rows = []
                action_rows = []

                def _add_row(target_list, key: str):
                    item = issue_table.get(key) or {}
                    target_list.append({
                        "Item": item.get('label', key),
                        "Feedback": str(item.get('feedback', 'N/A')),
                        "Rating": str(item.get('rating', 'N/A')),
                        "Action needed / Notes": item.get('notes', 'N/A') or 'N/A',
                    })

                _add_row(audit_rows, 'effort_issue')
                _add_row(audit_rows, 'rebuttal_issue')
                _add_row(audit_rows, 'releasing_issue')
                _add_row(audit_rows, 'tonality_issue')
                _add_row(action_rows, 'agents_coaching')
                _add_row(action_rows, 'agents_allocation')
                _add_row(action_rows, 'campaign_list')

                def _color_feedback(val: str) -> str:
                    if val == "Yes":
                        return 'background-color: rgba(248,113,113,0.35); color: #111827;'
                    if val == "No":
                        return 'background-color: rgba(74,222,128,0.35); color: #052e16;'
                    return ''

                def _color_rating(val: str) -> str:
                    if val == "High":
                        return 'background-color: rgba(248,113,113,0.35);'
                    if val == "Medium":
                        return 'background-color: rgba(250,204,21,0.35);'
                    if val == "Low":
                        return 'background-color: rgba(74,222,128,0.35);'
                    return ''

                def _render_table(rows_data, title: str):
                    df_local = pd.DataFrame(rows_data)
                    styled = df_local.style.applymap(_color_feedback, subset=["Feedback"]).applymap(
                        _color_rating, subset=["Rating"]
                    )
                    st.markdown(f"**{title}**")
                    st.dataframe(
                        styled,
                        width='stretch',
                        hide_index=True,
                    )

                if audit_rows:
                    _render_table(audit_rows, "Auditing feedback")
                if action_rows:
                    _render_table(action_rows, "Action Points")

                st.caption("Issue Rating Ratio: Low < 30%  |  Medium 30% - 50%  |  High > 50%")
                
                # AI-generated overall campaign summary (text box)
                ai_summary = report.get('ai_summary')
                if isinstance(ai_summary, str) and ai_summary.strip():
                    st.markdown("---")
                    st.markdown("#### AI Campaign Summary")
                    # Display as a text area with built-in copy option
                    st.text_area("Summary", value=ai_summary, height=200, key="ai_summary_text")
                
                
    # Clear data option - scoped to the selected campaign
    st.markdown("---")
    if st.button("Clear Selected Campaign Data", type="secondary"):
        if st.session_state.get('confirm_clear_campaign', False):
            dashboard_manager.clear_campaign_audit_data(
                st.session_state.get('username'),
                selected_campaign
            )
            st.success(f"Campaign audit data for '{selected_campaign}' cleared successfully!")
            # Clear the loaded data from session state
            if 'campaign_dashboard_data' in st.session_state:
                del st.session_state.campaign_dashboard_data
            st.rerun()
        else:
            st.session_state['confirm_clear_campaign'] = True
            st.warning("Click again to confirm clearing this campaign's audit data.")


def show_lite_audit_dashboard(dashboard_manager, generate_csv_data):
    """Display Lite Audit Dashboard with persistent data storage."""
    
    st.markdown("### Lite Audit Dashboard")
    
    # Add refresh button at the top
    col1, col2 = st.columns([3, 1])
    with col1:
        st.write("")  # Empty space
    with col2:
        if st.button("Refresh Data", help="Reload data from storage", key="lite_refresh_btn"):
            # Clear any cached data and force reload
            if 'lite_dashboard_cache_timestamp' in st.session_state:
                del st.session_state.lite_dashboard_cache_timestamp
            st.rerun()
    
    # Get combined lite audit data from current user's audits
    df = dashboard_manager.get_combined_lite_audit_data(st.session_state.get('username'))
    
    if df.empty:
        st.info("No lite audit data available. Run Lite Audits to see results here.")
        return
    
    # Filter to show ONLY flagged calls (calls with quality issues)
    # Use robust filtering that handles case variations, empty values, and whitespace
    if 'Releasing Detection' not in df.columns or 'Late Hello Detection' not in df.columns:
        st.warning("Missing detection columns in lite audit data. Please check data integrity.")
        st.dataframe(df.head() if not df.empty else pd.DataFrame(), width='stretch')
        return
    
    # Normalize columns to handle any data type issues
    df['Releasing Detection'] = df['Releasing Detection'].astype(str).str.strip()
    df['Late Hello Detection'] = df['Late Hello Detection'].astype(str).str.strip()
    
    # Case-insensitive filtering for flagged calls
    flagged_df = df[
        (df['Releasing Detection'].str.lower() == 'yes') |
        (df['Late Hello Detection'].str.lower() == 'yes')
    ].copy()
    
    if flagged_df.empty:
        st.info("No flagged calls found in lite audit data. All calls passed quality checks!")
        return
    
    # Use the filtered DataFrame for all subsequent operations
    df = flagged_df

    # Remove unwanted columns from display (keep in data for CSV export)
    # Match Agent Audit Dashboard: only remove File Name, File Path, Call Duration, Confidence Score, and internal columns
    # Note: 'username' is kept and will be displayed as "Auditor"
    columns_to_hide = [
        'File Name', 
        'File Path', 
        'Call Duration', 
        'Confidence Score',
        'audit_timestamp'
    ]
    display_df = df.copy()
    for col in columns_to_hide:
        if col in display_df.columns:
            display_df = display_df.drop(columns=[col])
    
    # Rename 'audit_type' to 'Audit Type' if it exists
    if 'audit_type' in display_df.columns:
        display_df = display_df.rename(columns={'audit_type': 'Audit Type'})

    # Define target columns in exact order (matching standard dashboard layout)
    target_columns = [
        "Agent Name",
        "Phone Number",
        "Timestamp",
        "Disposition",
        "Releasing Detection",
        "Late Hello Detection",
        "Rebuttal Detection",
        "Transcription",
        "Owner Name",
        "Agent Intro",
        "Reason for calling",
        "Intro Score",
        "Status",
        "Dialer Name",
        "Audit Type",
        "Auditor"
    ]
    
    # Handle column name variations (e.g., "dialer_name" vs "Dialer Name", "Reason for Calling" vs "Reason for calling")
    # Also rename 'username' to 'Auditor' for display
    column_name_mapping = {}
    
    # First, check for all possible column name variations and create mapping
    for col in display_df.columns:
        col_lower = col.lower().replace(' ', '').replace('_', '')
        # Check for "Reason for calling" variations
        if 'reason' in col_lower and 'calling' in col_lower and 'Reason for calling' not in display_df.columns:
            if col != 'Reason for calling':
                column_name_mapping[col] = 'Reason for calling'
        # Check for "Dialer Name" variations
        elif 'dialer' in col_lower and 'Dialer Name' not in display_df.columns:
            if col != 'Dialer Name':
                column_name_mapping[col] = 'Dialer Name'
        # Check for "Audit Type" variations
        elif ('audit' in col_lower and 'type' in col_lower) or col == 'audit_type':
            if col != 'Audit Type':
                column_name_mapping[col] = 'Audit Type'
        # Check for "Auditor" variations
        elif col == 'username':
            column_name_mapping[col] = 'Auditor'
    
    # Apply column name mappings first
    if column_name_mapping:
        display_df = display_df.rename(columns=column_name_mapping)
    
    # Now ensure all target columns exist (add missing ones)
    for target_col in target_columns:
        if target_col not in display_df.columns:
            if target_col in ["Rebuttal Detection", "Transcription", "Agent Intro", "Owner Name", "Intro Score", "Status", "Audit Type"]:
                display_df[target_col] = "N/A"
            else:
                display_df[target_col] = ""
    
    # Ensure all target columns are present before reordering
    for col in target_columns:
        if col not in display_df.columns:
            if col in ["Rebuttal Detection", "Transcription", "Agent Intro", "Owner Name", "Intro Score", "Status", "Audit Type"]:
                display_df[col] = "N/A"
            else:
                display_df[col] = ""
    
    # Reorder columns to match target order - ALL target columns should be present now
    # Force include all target columns in the correct order
    ordered_cols = []
    for col in target_columns:
        if col in display_df.columns:
            ordered_cols.append(col)
    
    # Add any remaining columns that aren't in the target order
    remaining_cols = [col for col in display_df.columns if col not in target_columns]
    
    # Final column order: target columns first (in correct order), then any remaining columns
    display_df = display_df[ordered_cols + remaining_cols]

    if 'Agent Name' in display_df.columns:
        display_df = display_df.sort_values('Agent Name', ascending=True, key=lambda col: col.str.lower()).reset_index(drop=True)

    # Display summary statistics for lite audits
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Calls", len(df))
    with col2:
        releasing_count = len(df[df['Releasing Detection'] == 'Yes'])
        st.metric("Releasing Calls", releasing_count)
    with col3:
        late_hello_count = len(df[df['Late Hello Detection'] == 'Yes'])
        st.metric("Late Hello Calls", late_hello_count)
    
    # Flagged calls summary (calls with ANY issue in lite mode)
    flagged_calls = len(df[
        (df['Releasing Detection'] == 'Yes') |
        (df['Late Hello Detection'] == 'Yes')
    ])
    
    st.markdown(f"**Flagged Calls**: {flagged_calls} calls with quality issues detected")
    
    # Display the data table with conditional styling for lite mode
    st.markdown("#### Detailed Results")
    
    # Apply conditional styling to highlight critical issues
    def highlight_lite_issues(row):
        """Apply conditional styling for lite audit issues."""
        styles = []
        for col in row.index:
            base_style = 'background-color: #000000; color: #ffffff; border: 1px solid rgba(255,255,255,0.08);'
            
            # Highlight critical combinations
            if col in ['Releasing Detection', 'Late Hello Detection']:
                if row[col] == 'Yes':
                    styles.append(f'{base_style} background-color: rgba(239, 68, 68, 0.2); border-left: 3px solid #ef4444;')
                else:
                    styles.append(f'{base_style} background-color: rgba(34, 197, 94, 0.1); border-left: 3px solid #22c55e;')
            else:
                styles.append(base_style)
        
        return styles

    def _make_unique_columns(df: pd.DataFrame) -> pd.DataFrame:
        cols = [str(c) for c in df.columns]
        if len(cols) == len(set(cols)):
            df.columns = cols
            return df

        seen = {}
        new_cols = []
        for c in cols:
            count = seen.get(c, 0) + 1
            seen[c] = count
            new_cols.append(c if count == 1 else f"{c} ({count})")

        df = df.copy()
        df.columns = new_cols
        return df
    
    if not display_df.empty:
        # Ensure unique indices before applying styling (fixes Styler.apply error)
        display_df = display_df.reset_index(drop=True)

        # Ensure unique column names for Streamlit/pyarrow conversion
        display_df = _make_unique_columns(display_df)
        
        try:
            styled_df = display_df.style.apply(highlight_lite_issues, axis=1)
            st.dataframe(styled_df, width='stretch')
        except Exception as e:
            logger.warning(f"Error applying styling, displaying without style: {e}")
            st.dataframe(display_df, width='stretch')
    else:
        display_df = _make_unique_columns(display_df.reset_index(drop=True))
        st.dataframe(display_df, width='stretch')

    # Download options - CSV only (respect visible columns)
    csv_data, filename = generate_csv_data(display_df, "lite_audit_dashboard")
    st.download_button(
        label="Download CSV",
        data=csv_data,
        file_name=filename,
        mime="text/csv",
    )
    
    # Clear lite audit data option
    st.markdown("---")
    if st.button("Clear All Lite Audit Data", type="secondary"):
        if st.session_state.get('confirm_clear_lite', False):
            dashboard_manager.clear_lite_audit_data(st.session_state.get('username'))
            st.success("Lite audit data cleared successfully!")
            st.rerun()
        else:
            st.session_state['confirm_clear_lite'] = True
            st.warning("Click again to confirm clearing all lite audit data.")


def show_actions_section(dashboard_manager):
    """Display the Actions section showing only flagged calls that need attention."""
    
    st.markdown("### Actions - Flagged Calls Requiring Attention")
    
    # Get current user
    current_username = st.session_state.get('username')
    if not current_username:
        st.error("Please log in to view actions.")
        return
    
    # Combine data from both agent audit and lite audit
    agent_df = dashboard_manager.get_combined_agent_audit_data(current_username)
    lite_df = dashboard_manager.get_combined_lite_audit_data(current_username)
    
    # Combine both dataframes
    combined_df = pd.concat([agent_df, lite_df], ignore_index=True) if not agent_df.empty and not lite_df.empty else (
        agent_df if not agent_df.empty else lite_df
    )
    
    if combined_df.empty:
        st.info("No audit data available. Run audits to see flagged calls that need attention.")
        return
    
    # Clean up duplicate/similar columns
    # Handle dialer name column properly: merge values from both columns
    if 'Dialer Name' in combined_df.columns and 'dialer_name' in combined_df.columns:
        # Both exist - create final dialer_name column with best values
        combined_df['dialer_name'] = combined_df['dialer_name'].fillna(combined_df['Dialer Name'])
        combined_df = combined_df.drop('Dialer Name', axis=1)
    elif 'Dialer Name' in combined_df.columns and 'dialer_name' not in combined_df.columns:
        # Only Dialer Name exists - rename to dialer_name
        combined_df = combined_df.rename(columns={'Dialer Name': 'dialer_name'})
    
    # Remove duplicate reason for calling column
    if 'Reason for calling' in combined_df.columns and 'Reason for Calling' in combined_df.columns:
        combined_df = combined_df.drop('Reason for calling', axis=1)
    
    # Fix audit_type column: set to "Heavy" for agent audit data, keep "lite" for lite audit data
    if 'audit_type' in combined_df.columns:
        # For rows where audit_type is None/NaN and we have agent audit data (has Rebuttal Detection column), set to "Heavy"
        mask_agent_audit = (combined_df['audit_type'].isna() | (combined_df['audit_type'] == 'None')) & combined_df['Rebuttal Detection'].notna()
        combined_df.loc[mask_agent_audit, 'audit_type'] = 'Heavy'
    else:
        # If audit_type column doesn't exist, create it
        combined_df['audit_type'] = 'Heavy'  # Default to Heavy for agent audit data
 
    # Audited dialers summary data for current user (used later in layout)
    dialer_df = pd.DataFrame(columns=["Dialer", "Audited Calls"])
    dialer_series = None
    if 'dialer_name' in combined_df.columns:
        dialer_series = combined_df['dialer_name']
    elif 'Dialer Name' in combined_df.columns:
        dialer_series = combined_df['Dialer Name']

    if dialer_series is not None:
        dialer_counts = (
            dialer_series.dropna()
            .astype(str)
            .str.strip()
            .replace('', pd.NA)
            .dropna()
            .value_counts()
        )

        if not dialer_counts.empty:
            dialer_df = dialer_counts.reset_index()
            dialer_df.columns = ["Dialer", "Audited Calls"]

    # Apply filtering: (Quality issues AND no rebuttals) OR (rebuttal issues)
    # For lite audit data that doesn't have Rebuttal Detection column, treat as "No rebuttal"
    quality_issues_mask = (
        (combined_df['Releasing Detection'] == 'Yes') | (combined_df['Late Hello Detection'] == 'Yes')
    )
    
    # Handle rebuttal logic: if column exists, check for "No" or "N/A" (lite audit), if not, treat as "No"
    if 'Rebuttal Detection' in combined_df.columns:
        no_rebuttal_mask = (combined_df['Rebuttal Detection'].isin(['No', 'N/A']))
        rebuttal_issues_mask = (combined_df['Rebuttal Detection'] == 'No')  # Only actual 'No' for agent audits
    else:
        # For data without rebuttal column, treat all as "No rebuttal"
        no_rebuttal_mask = pd.Series([True] * len(combined_df), index=combined_df.index)
        rebuttal_issues_mask = pd.Series([False] * len(combined_df), index=combined_df.index)
    
    # Include calls that have: (quality issues AND no rebuttals) OR (rebuttal issues)
    flagged_df = combined_df[
        ((quality_issues_mask & no_rebuttal_mask) | rebuttal_issues_mask)
    ].copy()
    
    if flagged_df.empty:
        # No message - just return silently
        return
    
    # Display summary
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Action Items", len(flagged_df))
    with col2:
        releasing_count = len(flagged_df[flagged_df['Releasing Detection'] == 'Yes'])
        st.metric("Releasing Issues", releasing_count)
    with col3:
        late_hello_count = len(flagged_df[flagged_df['Late Hello Detection'] == 'Yes'])
        st.metric("Late Hello Issues", late_hello_count)
    with col4:
        # Count calls with rebuttal issues (Rebuttal Detection = "No" only, not "N/A")
        rebuttal_issues = len(flagged_df[
            (flagged_df['Rebuttal Detection'] == 'No')
        ])
        st.metric("Rebuttal Issues", rebuttal_issues)
    
    # Filter out unwanted columns, keeping only columns that exist in the dataframe
    columns_to_remove = [
        'Agent Intro', 'Owner Name', 'Reason for Calling', 'Intro Score', 
        'Status', 'audit_timestamp', 'username', 'File Name'
    ]
    
    display_columns = [col for col in flagged_df.columns if col not in columns_to_remove]
    display_df = flagged_df[display_columns].copy()
    
    # Rename columns for better readability
    column_rename_map = {
        'dialer_name': 'Dialer',
        'audit_type': 'Audit Type'
    }
    display_df = display_df.rename(columns=column_rename_map)
    
    # Reorder columns for better readability and workflow clarity
    desired_order = [
        'Agent Name', 'Phone Number', 'Dialer', 'Releasing Detection', 
        'Late Hello Detection', 'Rebuttal Detection', 'Disposition', 
        'Transcription', 'Timestamp', 'Audit Type'
    ]
    
    # Only include columns that exist in the dataframe
    final_columns = [col for col in desired_order if col in display_df.columns]
    # Add any remaining columns that weren't in the desired order
    remaining_cols = [col for col in display_df.columns if col not in final_columns]
    final_columns.extend(remaining_cols)
    
    display_df = display_df[final_columns]
    
    # Mini-dashboard: Agent Deductions (per-agent flagged call summary)
    st.markdown("#### Agent Deductions")

    # Build per-agent statistics: Total Calls, Flagged Calls, Releasing, Late Hello, No Rebuttals, Deduction
    if 'Agent Name' in flagged_df.columns and not flagged_df.empty:
        # Total calls per agent from combined_df (all audited calls)
        if 'Agent Name' in combined_df.columns:
            total_calls_df = (
                combined_df.groupby('Agent Name')
                .size()
                .reset_index(name='Total Calls')
            )
        else:
            total_calls_df = pd.DataFrame(columns=['Agent Name', 'Total Calls'])

        # Flagged calls per agent (any issue)
        flagged_counts_df = (
            flagged_df.groupby('Agent Name')
            .size()
            .reset_index(name='Flagged Calls')
        )

        # Releasing issues per agent
        if 'Releasing Detection' in flagged_df.columns:
            releasing_counts_df = (
                flagged_df[flagged_df['Releasing Detection'] == 'Yes']
                .groupby('Agent Name')
                .size()
                .reset_index(name='Releasing')
            )
        else:
            releasing_counts_df = pd.DataFrame(columns=['Agent Name', 'Releasing'])

        # Late Hello issues per agent
        if 'Late Hello Detection' in flagged_df.columns:
            late_hello_counts_df = (
                flagged_df[flagged_df['Late Hello Detection'] == 'Yes']
                .groupby('Agent Name')
                .size()
                .reset_index(name='Late Hello')
            )
        else:
            late_hello_counts_df = pd.DataFrame(columns=['Agent Name', 'Late Hello'])

        # No Rebuttals per agent (only actual "No", not "N/A")
        if 'Rebuttal Detection' in flagged_df.columns:
            no_rebuttal_df = flagged_df[flagged_df['Rebuttal Detection'] == 'No']
            rebuttal_counts_df = (
                no_rebuttal_df.groupby('Agent Name')
                .size()
                .reset_index(name='No Rebuttals')
            )
        else:
            rebuttal_counts_df = pd.DataFrame(columns=['Agent Name', 'No Rebuttals'])

        # Start from agents with at least one flagged call
        agent_stats = flagged_counts_df.copy()

        # Merge in other stats
        agent_stats = agent_stats.merge(total_calls_df, on='Agent Name', how='left')
        agent_stats = agent_stats.merge(releasing_counts_df, on='Agent Name', how='left')
        agent_stats = agent_stats.merge(late_hello_counts_df, on='Agent Name', how='left')
        agent_stats = agent_stats.merge(rebuttal_counts_df, on='Agent Name', how='left')

        # Ensure numeric columns are integers and fill missing with 0
        for col in ['Total Calls', 'Flagged Calls', 'Releasing', 'Late Hello', 'No Rebuttals']:
            if col in agent_stats.columns:
                agent_stats[col] = agent_stats[col].fillna(0).astype(int)

        # Deduction rule: Yes if Flagged Calls >= 5, otherwise No
        agent_stats['Deduction'] = agent_stats['Flagged Calls'].apply(
            lambda x: 'Yes' if x >= 5 else 'No'
        )

        # Sort by Flagged Calls descending (most issues at the top)
        agent_stats = agent_stats.sort_values('Flagged Calls', ascending=False)

        # Reorder columns to match desired layout
        desired_cols = [
            'Agent Name', 'Total Calls', 'Flagged Calls',
            'Releasing', 'Late Hello', 'No Rebuttals', 'Deduction'
        ]
        existing_cols = [col for col in desired_cols if col in agent_stats.columns]
        remaining_cols = [col for col in agent_stats.columns if col not in existing_cols]
        agent_stats = agent_stats[existing_cols + remaining_cols]

        # Styling: highlight agents based on Deduction result
        def highlight_agent_deductions(row):
            styles = []
            base_style = 'background-color: #000000; color: #ffffff; border: 1px solid rgba(255,255,255,0.08);'
            flagged_calls = row.get('Flagged Calls', 0) or 0
            for col in row.index:
                style = base_style
                if col == 'Deduction':
                    deduction_value = row.get('Deduction')
                    if deduction_value == 'Yes':
                        # Hard deduction: highlight in red
                        style = f"{base_style} background-color: rgba(239, 68, 68, 0.3); border-left: 3px solid #ef4444; font-weight: bold;"
                    elif deduction_value == 'No':
                        if flagged_calls >= 5:
                            # Safety: if data inconsistent and >=5 but still No, treat as red
                            style = f"{base_style} background-color: rgba(239, 68, 68, 0.3); border-left: 3px solid #ef4444; font-weight: bold;"
                        elif flagged_calls >= 4:
                            # Close to threshold (e.g. 4 flagged calls): warning yellow
                            style = f"{base_style} background-color: rgba(251, 191, 36, 0.25); border-left: 3px solid #f59e0b; font-weight: bold;"
                        else:
                            # Safe zone: green
                            style = f"{base_style} background-color: rgba(34, 197, 94, 0.25); border-left: 3px solid #22c55e; font-weight: bold;"
                elif col == 'Flagged Calls' and flagged_calls >= 5:
                    # Keep red tint on high flagged count column
                    style = f"{base_style} background-color: rgba(239, 68, 68, 0.2); border-left: 3px solid #ef4444;"
                styles.append(style)
            return styles

        if not agent_stats.empty:
            styled_stats = agent_stats.style.apply(highlight_agent_deductions, axis=1)
            st.dataframe(styled_stats, width='stretch', hide_index=True)

            # Agent selection for detailed flagged calls (all agents with at least one flagged call)
            agent_options = agent_stats['Agent Name'].tolist()
            if agent_options:
                selected_agent = st.selectbox(
                    "Select agent to view detailed flagged calls",
                    agent_options,
                    key="agent_deductions_select",
                )
                agent_calls = flagged_df[flagged_df['Agent Name'] == selected_agent]
                if not agent_calls.empty:
                    lines = []
                    for _, row in agent_calls.iterrows():
                        phone = str(row.get('Phone Number', 'Unknown'))
                        if row.get('Releasing Detection') == 'Yes':
                            issue = "Releasing"
                        elif row.get('Late Hello Detection') == 'Yes':
                            issue = "Late Hello"
                        elif row.get('Rebuttal Detection') == 'No':
                            issue = "No Rebuttals"
                        else:
                            issue = "Issue"

                        dialer_value = row.get('dialer_name') or row.get('Dialer Name') or row.get('Dialer')
                        dialer = str(dialer_value) if dialer_value is not None else ""
                        dialer = dialer.strip()

                        if dialer:
                            lines.append(f"{phone} - {issue} - {dialer}")
                        else:
                            lines.append(f"{phone} - {issue}")

                    if lines:
                        col_left, col_right = st.columns([3, 2])
                        with col_left:
                            st.markdown(f"##### Detailed flagged calls for {selected_agent}")
                            st.code("\n".join(lines), language="")
                        with col_right:
                            if not dialer_df.empty:
                                st.markdown("##### Audited Dialers")
                                st.dataframe(dialer_df, hide_index=True, width="stretch")
                    else:
                        st.info("No detailed calls found for this agent.")
        else:
            st.dataframe(agent_stats, width='stretch', hide_index=True)

    else:
        st.info("No agent data available for deductions summary.")

    # Clear action items option
    st.markdown("---")
    if st.button("Clear All Data", type="secondary"):
        if st.session_state.get('confirm_clear_actions', False):
            # Clear both agent and lite audit data
            dashboard_manager.clear_agent_audit_data(st.session_state.get('username'))
            dashboard_manager.clear_lite_audit_data(st.session_state.get('username'))
            st.success("All agent and lite audit data cleared successfully!")
            st.info("The Actions section will now show no data until new audits are run.")
            st.rerun()
        else:
            st.session_state['confirm_clear_actions'] = True
            st.warning("**WARNING**: This will permanently delete ALL your audit data (both agent and lite audits). This action cannot be undone. Click again to confirm.")

