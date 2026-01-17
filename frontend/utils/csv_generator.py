"""
CSV generation utilities for data export.
"""
from datetime import datetime
from typing import Tuple
import pandas as pd
import streamlit as st
from config import CacheConfig


@st.cache_data(ttl=CacheConfig.CSV_TTL)
def generate_csv_data(df: pd.DataFrame, filename_prefix: str) -> Tuple[bytes, str]:
    """
    Generate and cache CSV data to prevent hash changes in download buttons.

    Args:
        df: DataFrame to convert to CSV
        filename_prefix: Prefix for the filename

    Returns:
        tuple: (csv_bytes, filename)
    """
    if df.empty:
        return b"", f"{filename_prefix}_empty.csv"

    csv_data = df.to_csv(index=False).encode("utf-8")
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"{filename_prefix}_{timestamp}.csv"

    return csv_data, filename
