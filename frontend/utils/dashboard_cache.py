"""
Caching utilities for VOS Railway dashboard data.
Reduces memory usage and database load by caching frequently accessed data.
"""

import streamlit as st
import pandas as pd
from datetime import date
from typing import Optional

# Cache TTL in seconds (5 minutes)
CACHE_TTL = 300


@st.cache_data(ttl=CACHE_TTL)
def get_cached_agent_audit_data(
    dashboard_manager,
    username: str,
    limit: int = 1000,
    offset: int = 0
) -> pd.DataFrame:
    """
    Cached wrapper for agent audit data loading.
    
    Args:
        dashboard_manager: DashboardManager instance
        username: Username to load data for
        limit: Maximum number of rows to return
        offset: Number of rows to skip
        
    Returns:
        DataFrame with agent audit results
    """
    return dashboard_manager.get_combined_agent_audit_data(
        username=username,
        limit=limit,
        offset=offset
    )


@st.cache_data(ttl=CACHE_TTL)
def get_cached_lite_audit_data(
    dashboard_manager,
    username: str,
    limit: int = 1000,
    offset: int = 0
) -> pd.DataFrame:
    """
    Cached wrapper for lite audit data loading.
    
    Args:
        dashboard_manager: DashboardManager instance
        username: Username to load data for
        limit: Maximum number of rows to return
        offset: Number of rows to skip
        
    Returns:
        DataFrame with lite audit results
    """
    return dashboard_manager.get_combined_lite_audit_data(
        username=username,
        limit=limit,
        offset=offset
    )


@st.cache_data(ttl=CACHE_TTL)
def get_cached_campaign_audit_data(
    dashboard_manager,
    campaign_name: str,
    start_date: date,
    end_date: date,
    username: str
) -> pd.DataFrame:
    """
    Cached wrapper for campaign audit data loading.
    
    Args:
        dashboard_manager: DashboardManager instance
        campaign_name: Name of the campaign
        start_date: Start date for filtering
        end_date: End date for filtering
        username: Username to load data for
        
    Returns:
        DataFrame with campaign audit results
    """
    return dashboard_manager.load_campaign_audit_data(
        campaign_name=campaign_name,
        start_date=start_date,
        end_date=end_date,
        username=username
    )


@st.cache_data(ttl=CACHE_TTL)
def get_cached_available_campaigns(
    dashboard_manager,
    username: Optional[str] = None
) -> list:
    """
    Cached wrapper for available campaigns list.
    
    Args:
        dashboard_manager: DashboardManager instance
        username: Username to load campaigns for
        
    Returns:
        List of available campaign names
    """
    return dashboard_manager.get_available_campaigns(username)


def clear_all_caches():
    """Clear all Streamlit caches to force data refresh."""
    st.cache_data.clear()
