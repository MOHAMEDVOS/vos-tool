import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime

def show_interactive_report(df: pd.DataFrame, report_data: dict):
    """
    Display the interactive Campaign Performance Report.
    
    Args:
        df: The raw audit dataframe.
        report_data: The dictionary returned by dashboard_manager.generate_performance_report()
    """
    if df.empty or not report_data:
        st.warning("No data available for interactive report.")
        return

    # Extract Key Data
    metric_summaries = report_data.get('metric_summaries', {})
    agent_details = report_data.get('agent_performance_details', {})
    quality_dist = report_data.get('quality_score_distribution', {})
    avg_score = report_data.get('average_quality_score', 0)
    audit_counts = report_data.get('audit_counts', {})
    
    # ---------------------------------------------------------
    # 1. SIDEBAR FILTERS
    # ---------------------------------------------------------
    with st.sidebar:
        st.header("🔍 Report Filters")
        
        # Agent Filter
        all_agents = sorted(df['Agent Name'].dropna().unique().tolist())
        selected_agents = st.multiselect(
            "Filter Agents",
            options=all_agents,
            default=all_agents,
            key="report_agent_filter"
        )
        
        # Performance Filter
        perf_options = ["All", "Critical (< 80%)", "Needs Improvement (80-90%)", "Excellent (> 90%)"]
        perf_filter = st.selectbox("Performance Level", perf_options, key="report_perf_filter")
        
        # Filter Logic
        filtered_df = df[df['Agent Name'].isin(selected_agents)]
        
        if perf_filter != "All":
            # This requires calculating agent scores dynamically or filtering the agent_details list
            # For simplicity, we filter the AGENT VIEW, not necessarily the global df immediately
            pass

    # ---------------------------------------------------------
    # 2. TOP METRICS CARDS
    # ---------------------------------------------------------
    st.markdown("### 📊 Campaign Performance Dashboard")
    
    col1, col2, col3, col4 = st.columns(4)
    
    # Calculate Critical Agents count
    critical_count = 0
    for agent, stats in agent_details.items():
        if stats.get('average_score', 0) < 80:
            critical_count += 1
            
    # Success Rate (Calls with > 90% score ?) Or just 100% scores?
    # Let's use Quality Score > 80% as "Success"
    success_count = 0
    total_scored = 0
    if 'Intro Score' in filtered_df.columns:
        for score in filtered_df['Intro Score']:
            try:
                if pd.isna(score) or str(score) == 'N/A': continue
                val = float(str(score).replace('%',''))
                total_scored += 1
                if val >= 80:
                    success_count += 1
            except: continue
    
    success_rate = int((success_count / total_scored * 100)) if total_scored > 0 else 0

    with col1:
        st.metric(label="📞 Total Calls", value=len(filtered_df))
    
    with col2:
        st.metric(label="⭐ Avg Quality Score", value=f"{int(avg_score)}%")
        
    with col3:
        st.metric(label="🚨 Critical Agents", value=str(critical_count), delta_color="inverse")
        
    with col4:
        st.metric(label="✅ Success Rate", value=f"{success_rate}%")

    st.divider()

    # ---------------------------------------------------------
    # 3. TABS LAYOUT
    # ---------------------------------------------------------
    tab_overview, tab_agents, tab_calls = st.tabs(["📊 Overview", "👥 Agent Performance", "📞 Call Drill-Down"])

    # === TAB 1: OVERVIEW ===
    with tab_overview:
        # A. Executive Summary (LLM Narrative)
        with st.expander("📋 EXECUTIVE SUMMARY (AI Generated)", expanded=True):
             llm_narrative = report_data.get('llm_narrative', "No narrative available.")
             st.markdown(llm_narrative)

        # B. Donut Charts for Key Metrics
        st.subheader("Key Performance Indicators")
        
        # Helper for Chart
        def create_donut(good, bad, title):
            # Safe handling if metrics are missing
            if good + bad == 0:
                values = [1, 0] # Dummy
                labels = ['No Data', '']
                colors = ['#cccccc', '#ffffff']
            else:
                values = [good, bad]
                labels = ['Good', 'Bad']
                colors = ['#00D26A', '#FF4B4B']
                
            fig = go.Figure(data=[go.Pie(
                labels=labels,
                values=values,
                hole=.6,
                marker_colors=colors,
                textinfo='percent',
                hoverinfo='label+value'
            )])
            fig.update_layout(
                title_text=title,
                title_x=0.5,
                showlegend=False,
                height=250,
                margin=dict(t=30, b=0, l=0, r=0)
            )
            return fig

        # Rows of charts
        m_cols1, m_cols2, m_cols3 = st.columns(3)
        
        # Late Hello
        lh_stats = metric_summaries.get('Late Hello', {'good_count': 0, 'bad_count': 0})
        with m_cols1:
            st.plotly_chart(create_donut(lh_stats.get('good_count',0), lh_stats.get('bad_count',0), "Late Hello Compliance"), use_container_width=True)

        # Rebuttals
        rb_stats = metric_summaries.get('Rebuttals', {'good_count': 0, 'bad_count': 0})
        with m_cols2:
             st.plotly_chart(create_donut(rb_stats.get('good_count',0), rb_stats.get('bad_count',0), "Rebuttal Usage"), use_container_width=True)

        # Releasing
        rl_stats = metric_summaries.get('Early Call Release', {'good_count': 0, 'bad_count': 0})
        with m_cols3:
             st.plotly_chart(create_donut(rl_stats.get('good_count',0), rl_stats.get('bad_count',0), "Call Completion (No Release)"), use_container_width=True)
             
        # Second Row
        m_cols4, m_cols5, m_cols6 = st.columns(3)
        
        # Intro
        intro_stats = metric_summaries.get('Agent Introduction', {'good_count': 0, 'bad_count': 0})
        with m_cols4:
             st.plotly_chart(create_donut(intro_stats.get('good_count',0), intro_stats.get('bad_count',0), "Agent Introduction"), use_container_width=True)

        # Reason
        reason_stats = metric_summaries.get('Reason for Calling', {'good_count': 0, 'bad_count': 0})
        with m_cols5:
             st.plotly_chart(create_donut(reason_stats.get('good_count',0), reason_stats.get('bad_count',0), "Reason Stated"), use_container_width=True)
             
        # Owner Name
        owner_stats = metric_summaries.get('Owner Name Confirmation', {'good_count': 0, 'bad_count': 0})
        with m_cols6:
             st.plotly_chart(create_donut(owner_stats.get('good_count',0), owner_stats.get('bad_count',0), "Owner Confirmation"), use_container_width=True)


    # === TAB 2: AGENT PERFORMANCE ===
    with tab_agents:
        st.subheader("Agent Scorecards")
        
        # Sort agents by score ascending (Problem agents first)
        sorted_agents = sorted(agent_details.items(), key=lambda x: x[1].get('average_score', 0))
        
        for agent_name, stats in sorted_agents:
            # Filter Logic within loop
            if agent_name not in selected_agents:
                continue
            
            score = stats.get('average_score', 0)
            
            # Status Icon & Color
            if score < 80:
                status_icon = "🚨"
                border_color = "3px solid #FF4B4B"
            elif score < 90:
                status_icon = "⚠️"
                border_color = "3px solid #FFA500"
            else:
                status_icon = "✅"
                border_color = "3px solid #00D26A"
            
            # Card Container
            with st.container():
                # Custom CSS-like styling using markdown for the header
                st.markdown(f"""
                <div style="border-left: {border_color}; padding-left: 10px; margin-bottom: 5px;">
                    <h3 style="margin:0;">{status_icon} {agent_name}</h3>
                </div>
                """, unsafe_allow_html=True)
                
                # Metrics Row
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Calls Reviewed", stats.get('total_calls', 0))
                c1.metric("Avg Score", f"{int(score)}%")
                
                # Get specific failure rates
                failures = stats.get('metric_failures', {})
                
                # Intro Failure
                intro_f = failures.get('Agent Introduction', {})
                intro_rate = intro_f.get('fail_rate', 0)
                intro_score = 100 - intro_rate
                c2.metric("Intro Compliance", f"{int(intro_score)}%")
                
                # Rebuttal Usage
                reb_f = failures.get('Rebuttals', {})
                reb_rate = reb_f.get('fail_rate', 0)
                reb_score = 100 - reb_rate
                # Check for N/A (if total is 0)
                reb_txt = f"{int(reb_score)}%" if reb_f.get('total', 0) > 0 else "N/A"
                c3.metric("Rebuttal Usage", reb_txt)

                # Drill Down Button
                c4.write("") # Spacer
                if c4.button("🔍 View Calls", key=f"btn_{agent_name}"):
                    st.session_state.report_selected_agent = agent_name
                    # Force switch to tab 3 (hacky but works if user manually clicks tab, strict navigation needs rerun)
                    st.success(f"Selected {agent_name}. Switch to 'Call Drill-Down' tab to view details.")

                st.divider()

    # === TAB 3: CALL DRILL-DOWN ===
    with tab_calls:
        
        # Check if agent selected
        target_agent = st.session_state.get('report_selected_agent')
        
        col_header, col_clear = st.columns([4,1])
        with col_header:
            st.subheader(f"Call Details: {target_agent if target_agent else 'All Agents'}")
        with col_clear:
            if st.button("Reset Selection"):
                st.session_state.report_selected_agent = None
                st.rerun()

        # Prepare Data Table
        display_cols = [
            'Agent Name', 'Phone Number', 'Timestamp', 'Intro Score', 
            'Rebuttal Detection', 'Releasing Detection', 'Late Hello Detection', 
            'Agent Intro', 'Reason for calling'
        ]
        
        # Filter for selected agent
        drill_df = filtered_df.copy()
        if target_agent:
            drill_df = drill_df[drill_df['Agent Name'] == target_agent]
            
        # Show Dataframe
        st.dataframe(
            drill_df[display_cols] if not drill_df.empty else pd.DataFrame(),
            use_container_width=True,
            hide_index=True
        )
        
        # Transcript Viewer
        st.markdown("### 📝 Transcript Viewer")
        call_options = drill_df['Phone Number'].astype(str).tolist()
        
        if call_options:
            selected_phone = st.selectbox("Select Call to Review", call_options)
            
            if selected_phone:
                call_record = drill_df[drill_df['Phone Number'].astype(str) == selected_phone].iloc[0]
                
                # Layout: Metadata Left, Transcript Right
                tc1, tc2 = st.columns([1, 2])
                
                with tc1:
                    st.info(f"**Agent:** {call_record['Agent Name']}")
                    st.write(f"**Score:** {call_record.get('Intro Score', 'N/A')}")
                    st.write(f"**Rebuttal:** {call_record.get('Rebuttal Detection', 'N/A')}")
                    st.write(f"**Intro:** {call_record.get('Agent Intro', 'N/A')}")
                    st.write(f"**Reason:** {call_record.get('Reason for calling', 'N/A')}")
                    
                with tc2:
                    st.markdown("**Transcript:**")
                    transcript_text = call_record.get('Transcription', 'No transcript available.')
                    st.text_area("", value=transcript_text, height=300, disabled=True)
                    
                    st.markdown("**AI Feedback:**")
                    st.info(call_record.get('Feedback', 'No feedback available.'))
        else:
            st.info("No calls available for the selected agent.")
