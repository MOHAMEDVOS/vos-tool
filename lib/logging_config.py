"""
Centralized logging configuration for the application.
"""
import logging
import sys
from typing import Optional


def setup_logging(
    level: int = logging.INFO,
    format_string: Optional[str] = None,
    stream: Optional[object] = None
) -> None:
    """
    Configure application-wide logging.
    
    Args:
        level: Logging level (default: INFO)
        format_string: Custom format string. If None, uses default format.
        stream: Output stream. If None, uses sys.stderr.
    """
    if format_string is None:
        format_string = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    
    if stream is None:
        stream = sys.stderr
    
    logging.basicConfig(
        level=level,
        format=format_string,
        handlers=[logging.StreamHandler(stream)],
        force=True  # Override any existing configuration
    )


def setup_frontend_logging() -> None:
    """
    Configure logging for Streamlit frontend (simpler format).
    """
    logging.basicConfig(
        level=logging.WARNING,  # Reduce verbosity for frontend
        format='%(message)s',  # Simple format without timestamps
        handlers=[logging.StreamHandler()],
        force=True
    )


def setup_backend_logging() -> None:
    """
    Configure logging for FastAPI backend (detailed format).
    """
    setup_logging(
        level=logging.INFO,
        format_string='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
