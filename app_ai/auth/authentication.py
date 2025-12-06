from lib.dashboard_manager import session_manager
import streamlit as st


def check_authentication() -> bool:
    """Check if user is authenticated by validating session state."""

    authenticated = st.session_state.get("authenticated", False)
    username = st.session_state.get("username")
    session_id = st.session_state.get("session_id")

    if not authenticated or not username or not session_id:
        return False

    # Validate session with session manager
    if not session_manager.validate_session(username, session_id):
        # Session is invalid, clear local session state
        st.session_state.session_invalidated = True
        if "authenticated" in st.session_state:
            del st.session_state.authenticated
        if "username" in st.session_state:
            del st.session_state.username
        if "session_id" in st.session_state:
            del st.session_state.session_id
        return False

    return True


def is_user_authenticated() -> bool:
    """Lightweight check based on session state only (no server validation)."""

    return bool(
        st.session_state.get("authenticated", False)
        and st.session_state.get("username")
        and st.session_state.get("session_id")
    )


def get_current_username(default: str | None = None):
    """Return the current username from session state, or a default if provided."""

    if default is None:
        return st.session_state.get("username")
    return st.session_state.get("username", default)


def get_current_user_role(user_manager, default_username: str = "Unknown"):
    """Return the current user's role using user_manager, or None if unavailable."""

    username = get_current_username(default_username)
    if not username:
        return None
    return user_manager.get_user_role(username)


def logout_current_user(clear_auth_state: bool = True) -> None:
    """Invalidate the current user's session and optionally clear auth keys.

    This is a convenience wrapper around session_manager.invalidate_session
    for the *current* user stored in st.session_state.
    """

    username = st.session_state.get("username")
    session_id = st.session_state.get("session_id")

    if username and session_id:
        try:
            session_manager.invalidate_session(username, session_id)
        except Exception:
            # Best-effort invalidation; do not crash logout flow
            pass

    if clear_auth_state:
        for key in ["authenticated", "username", "session_id", "session_invalidated"]:
            if key in st.session_state:
                del st.session_state[key]


def logout_user_by_name(username: str) -> None:
    """Invalidate any active session for the given username.

    Used by the header URL-based logout flow, where we may not
    have full local session state but do know the target username.
    """

    if not username:
        return

    session_id = None
    try:
        session_id = session_manager.check_existing_session(username)
    except Exception:
        session_id = None

    if session_id:
        try:
            session_manager.invalidate_session(username, session_id)
        except Exception:
            # Best-effort invalidation
            pass

