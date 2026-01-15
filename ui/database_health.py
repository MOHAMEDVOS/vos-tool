"""
Database Health Monitoring Dashboard for VOS Tool
Displays real-time database metrics, connection pool status, and performance data.
"""

import streamlit as st
import time
from datetime import datetime
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)


def show_database_health_page():
    """Display the database health monitoring dashboard (Owner-only access)."""
    
    # Import authentication functions
    try:
        from frontend.app_ai.auth.authentication import get_current_username, get_current_user_role
        from lib.dashboard_manager import user_manager
    except ImportError:
        st.error("❌ Authentication system not available")
        return
    
    # Verify Owner access
    current_username = get_current_username("Unknown")
    current_user_role = get_current_user_role(user_manager) or user_manager.get_user_role(current_username)
    
    if current_user_role != "Owner":
        st.error("🔒 **Access Denied**: Database Health Monitoring is only available to Owner users.")
        st.info("This page contains sensitive system information and is restricted to system administrators.")
        return
    
    st.title("🏥 Database Health Monitor")
    st.markdown("Real-time monitoring of PostgreSQL database performance and health")
    
    try:
        from lib.db_health_monitor import get_health_monitor
        
        monitor = get_health_monitor()
        if not monitor:
            st.error("❌ Health monitor not available. Database manager may not be initialized.")
            return
        
        # Auto-refresh toggle
        col1, col2 = st.columns([3, 1])
        with col1:
            st.markdown("---")
        with col2:
            auto_refresh = st.checkbox("Auto-refresh (5s)", value=False)
        
        if auto_refresh:
            time.sleep(5)
            st.rerun()
        
        # Get health summary
        summary = monitor.get_health_summary()
        health_check = summary['health_check']
        pool_metrics = summary['pool_metrics']
        query_metrics = summary['query_metrics']
        alerts = summary['alerts']
        
        # Overall Status Banner
        overall_status = health_check['overall_status']
        status_color = {
            'HEALTHY': '🟢',
            'WARNING': '🟡',
            'CRITICAL': '🔴',
            'ERROR': '⚫'
        }.get(overall_status, '⚪')
        
        st.markdown(f"## {status_color} Overall Status: **{overall_status}**")
        st.caption(f"Last updated: {summary['timestamp']}")
        
        # Active Alerts
        if alerts:
            st.markdown("### ⚠️ Active Alerts")
            for alert in alerts:
                alert_emoji = {
                    'CRITICAL': '🔴',
                    'WARNING': '🟡',
                    'INFO': 'ℹ️'
                }.get(alert['level'], '⚪')
                
                st.warning(f"{alert_emoji} **{alert['level']}**: {alert['message']}")
        
        st.markdown("---")
        
        # Metrics Row 1: Connection Pool
        st.markdown("### 📊 Connection Pool Metrics")
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            pool_status = pool_metrics.get('health_status', 'UNKNOWN')
            status_emoji = {
                'HEALTHY': '🟢',
                'WARNING': '🟡',
                'CRITICAL': '🔴'
            }.get(pool_status, '⚪')
            st.metric("Pool Status", f"{status_emoji} {pool_status}")
        
        with col2:
            usage_percent = pool_metrics.get('usage_percent', 0.0)
            st.metric("Pool Usage", f"{usage_percent:.1f}%")
        
        with col3:
            used = pool_metrics.get('used_connections', 0)
            max_conn = pool_metrics.get('max_connections', 0)
            st.metric("Connections", f"{used}/{max_conn}")
        
        with col4:
            available = pool_metrics.get('available_connections', 0)
            st.metric("Available", f"{available}")
        
        # Pool usage progress bar
        if pool_metrics.get('max_connections', 0) > 0:
            st.progress(usage_percent / 100.0)
        
        st.markdown("---")
        
        # Metrics Row 2: Query Performance
        st.markdown("### 📈 Query Performance Metrics")
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            total_queries = query_metrics.get('total_queries', 0)
            st.metric("Total Queries", f"{total_queries:,}")
        
        with col2:
            success_rate = query_metrics.get('success_rate', 0.0)
            st.metric("Success Rate", f"{success_rate:.1f}%")
        
        with col3:
            avg_time = query_metrics.get('avg_query_time_ms', 0.0)
            st.metric("Avg Query Time", f"{avg_time:.2f}ms")
        
        with col4:
            slow_queries = query_metrics.get('slow_queries', 0)
            st.metric("Slow Queries", f"{slow_queries}")
        
        st.markdown("---")
        
        # Detailed Health Checks
        st.markdown("### 🔍 Detailed Health Checks")
        checks = health_check.get('checks', {})
        
        for check_name, check_result in checks.items():
            status = check_result.get('status', 'UNKNOWN')
            status_emoji = {
                'PASS': '✅',
                'HEALTHY': '✅',
                'WARNING': '⚠️',
                'FAIL': '❌',
                'CRITICAL': '🔴',
                'ERROR': '⚫'
            }.get(status, '⚪')
            
            with st.expander(f"{status_emoji} {check_name.replace('_', ' ').title()} - {status}"):
                if 'message' in check_result:
                    st.write(check_result['message'])
                
                # Display additional metrics for specific checks
                if check_name == 'connection_pool':
                    st.write(f"**Usage:** {check_result.get('usage_percent', 0):.1f}%")
                    st.write(f"**Used:** {check_result.get('used_connections', 0)}")
                    st.write(f"**Max:** {check_result.get('max_connections', 0)}")
                elif check_name == 'query_performance':
                    st.write(f"**Error Rate:** {check_result.get('error_rate', 0):.2f}%")
                    st.write(f"**Avg Time:** {check_result.get('avg_query_time_ms', 0):.2f}ms")
                    st.write(f"**Slow Queries:** {check_result.get('slow_queries', 0)}")
        
        st.markdown("---")
        
        # Slow Queries Table
        st.markdown("### 🐌 Recent Slow Queries")
        slow_queries_list = summary.get('slow_queries', [])
        
        if slow_queries_list:
            import pandas as pd
            
            df = pd.DataFrame(slow_queries_list)
            df['duration'] = df['duration'].apply(lambda x: f"{x:.3f}s")
            df['query'] = df['query'].apply(lambda x: x[:80] + "..." if len(x) > 80 else x)
            df['success'] = df['success'].apply(lambda x: "✅" if x else "❌")
            
            st.dataframe(
                df[['timestamp', 'duration', 'success', 'query']],
                use_container_width=True,
                hide_index=True
            )
        else:
            st.info("No slow queries recorded")
        
        st.markdown("---")
        
        # Configuration
        with st.expander("⚙️ Monitoring Configuration"):
            config = summary.get('monitoring_config', {})
            st.write(f"**Slow Query Threshold:** {config.get('slow_query_threshold_seconds', 1.0)}s")
            st.write(f"**Max Slow Queries Stored:** {config.get('max_slow_queries_stored', 100)}")
            
            st.markdown("**Alert Thresholds:**")
            thresholds = config.get('alert_thresholds', {})
            for key, value in thresholds.items():
                st.write(f"- {key.replace('_', ' ').title()}: {value}")
        
        # Actions
        st.markdown("---")
        st.markdown("### 🔧 Actions")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if st.button("🔄 Refresh Now"):
                st.rerun()
        
        with col2:
            if st.button("🗑️ Reset Metrics"):
                monitor.reset_metrics()
                st.success("Metrics reset successfully!")
                time.sleep(1)
                st.rerun()
        
        with col3:
            if st.button("📥 Export Report"):
                import json
                report_json = json.dumps(summary, indent=2, default=str)
                st.download_button(
                    label="Download JSON",
                    data=report_json,
                    file_name=f"db_health_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                    mime="application/json"
                )
        
    except Exception as e:
        st.error(f"❌ Error loading health monitor: {e}")
        logger.error(f"Database health page error: {e}", exc_info=True)


if __name__ == "__main__":
    # For standalone testing
    show_database_health_page()
