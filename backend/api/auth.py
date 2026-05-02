"""
Authentication API endpoints.
"""

from fastapi import APIRouter, HTTPException, status, Depends
from fastapi.responses import RedirectResponse
from fastapi.security import HTTPBearer
from typing import Optional
import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend.models.schemas import LoginRequest, LoginResponse, UserInfo
from backend.core.security import create_access_token, generate_session_id
from backend.core.dependencies import get_current_user
from lib.dashboard_manager import session_manager, user_manager
from lib.quota_manager import quota_manager
from backend.core.whitelist import get_user_from_whitelist
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
from google_auth_oauthlib.flow import Flow
import logging

logger = logging.getLogger(__name__)

router = APIRouter()
security = HTTPBearer()


@router.post("/google", response_model=LoginResponse)
async def google_login(request: dict):
    """Authenticate user using Google ID token."""
    try:
        credential = request.get("credential")
        if not credential:
            raise HTTPException(status_code=400, detail="Missing credential")

        # Verify Google token
        from backend.core.config import settings
        client_id = settings.GOOGLE_CLIENT_ID
        try:
            # Use 10s clock skew to handle 'Token used too early' errors (server/client clock mismatch)
            idinfo = id_token.verify_oauth2_token(credential, google_requests.Request(), client_id, clock_skew_in_seconds=10)
            email = idinfo['email']
            name = idinfo.get('name', '')
            picture = idinfo.get('picture', '')
        except Exception as e:
            logger.error(f"Google token verification failed: {e}")
            raise HTTPException(status_code=401, detail="Invalid Google token")

        # Check whitelist
        whitelisted_user = await get_user_from_whitelist(email)
        if not whitelisted_user:
            logger.warning(f"Unauthorized login attempt: {email}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Your account is not authorized. Contact administrator."
            )

        # Map to VOS role
        role = whitelisted_user["role"]
        
        # Ensure the primary owner always has Owner role regardless of whitelist
        if email.lower() == "mohamedibrahimpayonner@gmail.com":
            role = "Owner"
            
        readymode_user = whitelisted_user.get("readymode_user")
        readymode_password = whitelisted_user.get("readymode_password")
        
        # Ensure user exists in VOS user_manager (auto-provision)
        if not user_manager.user_exists(email):
            # Create user
            user_data = {
                "role": role,
                "name": name,
                "readymode_user": readymode_user,
                "readymode_pass": readymode_password
            }
            # Set unlimited quota for Owner
            if role == "Owner":
                user_data["daily_limit"] = 999999
                
            user_manager.add_user(email, user_data)
        else:
            # Sync role and readymode credentials if it changed
            update_data = {}
            current_user = user_manager.get_user(email)
            if current_user:
                if current_user.get("role") != role:
                    update_data["role"] = role
                if current_user.get("readymode_user") != readymode_user:
                    update_data["readymode_user"] = readymode_user
                
                if readymode_password:
                    update_data["readymode_pass"] = readymode_password
                
                # Ensure Owner has unlimited quota
                if role == "Owner" and current_user.get("daily_limit") != 999999:
                    update_data["daily_limit"] = 999999
                    
            if update_data:
                user_manager.update_user(email, update_data)

        # Sync quota_manager assignment (ensure Owner has 999999)
        if role == "Owner":
            try:
                # Assign to 'admin' group by default if no assignment exists or quota is wrong
                quota_status = quota_manager.get_user_quota_status(email)
                if not quota_status.get("has_quota") or quota_status.get("daily_quota") != 999999:
                    quota_manager.assign_user_to_admin(email, "admin", daily_quota=999999)
            except Exception as q_err:
                logger.error(f"Failed to sync quota for owner {email}: {q_err}")

        # Create session
        session_id = generate_session_id()
        session_manager.create_session(email, session_id)
        
        # Create JWT token
        access_token = create_access_token(data={
            "sub": email,
            "session_id": session_id
        })
        
        return LoginResponse(
            access_token=access_token,
            username=email,
            name=name,
            picture=picture,
            role=role,
            session_id=session_id
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Google login error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Google login failed"
        )


@router.post("/logout")
async def logout(current_user: dict = Depends(get_current_user)):
    """Logout current user and invalidate session."""
    try:
        username = current_user["username"]
        # Invalidate all sessions for the user (pass None as session_id to invalidate all)
        session_manager.invalidate_session(username, session_id=None)
        
        return {"message": "Logged out successfully"}
    except Exception as e:
        logger.error(f"Logout error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Logout failed"
        )


@router.get("/me", response_model=UserInfo)
async def get_current_user_info(current_user: dict = Depends(get_current_user)):
    """Get current user information."""
    user_data = current_user["user_data"]
    return UserInfo(
        username=current_user["username"],
        role=current_user["role"],
        daily_limit=user_data.get("daily_limit")
    )


@router.get("/session")
async def check_session(current_user: dict = Depends(get_current_user)):
    """Check whether the caller's authenticated JWT/session pair is valid."""
    return {
        "valid": True,
        "username": current_user["username"],
    }


_WORKSPACE_SCOPES = [
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/documents",
    "https://www.googleapis.com/auth/spreadsheets",
]


def _build_workspace_flow(redirect_uri: str) -> Flow:
    from backend.core.config import settings
    return Flow.from_client_config(
        {
            "web": {
                "client_id": settings.GOOGLE_CLIENT_ID,
                "client_secret": settings.GOOGLE_CLIENT_SECRET,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
            }
        },
        scopes=_WORKSPACE_SCOPES,
        redirect_uri=redirect_uri,
    )


@router.get("/google/workspace/connect")
async def google_workspace_connect(current_user: dict = Depends(get_current_user)):
    """Start the Google Workspace OAuth flow for Sheets/Docs/Drive access."""
    from backend.core.config import settings
    flow = _build_workspace_flow(settings.GOOGLE_OAUTH_REDIRECT_URI)
    auth_url, _ = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
        state=current_user["username"],
    )
    return {"auth_url": auth_url}


@router.get("/google/workspace/callback")
async def google_workspace_callback(code: str, state: str):
    """Handle OAuth callback, persist refresh token."""
    from backend.core.config import settings
    from lib.database import get_db_manager
    from lib.security_utils import SecurityManager

    flow = _build_workspace_flow(settings.GOOGLE_OAUTH_REDIRECT_URI)
    flow.fetch_token(code=code)
    creds = flow.credentials

    db = get_db_manager()
    if db is None:
        raise HTTPException(status_code=503, detail="Database unavailable")

    sec = SecurityManager()
    encrypted_refresh = sec.encrypt_string(creds.refresh_token) if creds.refresh_token else ""

    db.execute_query(
        """
        INSERT INTO user_google_tokens (username, access_token, refresh_token_encrypted, expires_at, scopes, updated_at)
        VALUES (%s, %s, %s, %s, %s, NOW())
        ON CONFLICT (username) DO UPDATE
            SET access_token = EXCLUDED.access_token,
                refresh_token_encrypted = EXCLUDED.refresh_token_encrypted,
                expires_at = EXCLUDED.expires_at,
                scopes = EXCLUDED.scopes,
                updated_at = NOW()
        """,
        (state, creds.token, encrypted_refresh, creds.expiry, " ".join(_WORKSPACE_SCOPES)),
        fetch=False,
    )

    # Close popup and notify the opener
    return RedirectResponse(url="/auth-success")


@router.get("/google/workspace/status")
async def google_workspace_status(current_user: dict = Depends(get_current_user)):
    """Return whether the current user has connected Google Workspace."""
    from lib.database import get_db_manager
    db = get_db_manager()
    if db is None:
        return {"connected": False}
    row = db.execute_query(
        "SELECT username FROM user_google_tokens WHERE username = %s",
        (current_user["username"],),
        fetchone=True,
    )
    return {"connected": bool(row)}
