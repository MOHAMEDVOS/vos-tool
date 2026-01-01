"""
Authentication module for Streamlit frontend using API client.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

import streamlit as st
from frontend.api_client import get_api_client
import logging

logger = logging.getLogger(__name__)


def check_authentication() -> bool:
    """Check if user is authenticated by validating session state and API session."""
    authenticated = st.session_state.get("authenticated", False)
    username = st.session_state.get("username")
    access_token = st.session_state.get("access_token")

    if not authenticated or not username or not access_token:
        return False

    # Validate session with backend API - pass session_id to validate specific session
    try:
        api_client = get_api_client()
        session_id = st.session_state.get("session_id")
        # Pass session_id to validate the specific session (not just any session)
        session_info = api_client.check_session(session_id=session_id)
        if not session_info.get("valid", False):
            # Session is invalid, clear local session state
            st.session_state.session_invalidated = True
            for key in ["authenticated", "username", "session_id", "access_token", "role"]:
                if key in st.session_state:
                    del st.session_state[key]
            return False
        return True
    except Exception as e:
        logger.error(f"Session validation error: {e}")
        # On error, assume invalid
        for key in ["authenticated", "username", "session_id", "access_token", "role"]:
            if key in st.session_state:
                del st.session_state[key]
        return False


def is_user_authenticated() -> bool:
    """Lightweight check based on session state only (no server validation)."""
    return bool(
        st.session_state.get("authenticated", False)
        and st.session_state.get("username")
        and st.session_state.get("access_token")
    )


def get_current_username(default: str | None = None):
    """Return the current username from session state, or a default if provided."""
    if default is None:
        return st.session_state.get("username")
    return st.session_state.get("username", default)


def get_current_user_role(default_username: str = "Unknown"):
    """Return the current user's role from session state."""
    username = get_current_username(default_username)
    if not username:
        return None
    return st.session_state.get("role")


def logout_current_user(clear_auth_state: bool = True) -> None:
    """Invalidate the current user's session via API and clear local state."""
    try:
        api_client = get_api_client()
        if st.session_state.get("access_token"):
            api_client.logout()
    except Exception as e:
        logger.error(f"Logout error: {e}")
        # Continue with local cleanup even if API call fails

    if clear_auth_state:
        for key in ["authenticated", "username", "session_id", "access_token", "role", "session_invalidated"]:
            if key in st.session_state:
                del st.session_state[key]


def logout_user_by_name(username: str) -> None:
    """Invalidate any active session for the given username."""
    # This would require admin API endpoint - for now, just clear local state
    # In a full implementation, this would call an admin API endpoint
    if username == st.session_state.get("username"):
        logout_current_user()
