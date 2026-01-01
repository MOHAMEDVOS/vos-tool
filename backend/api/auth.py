"""
Authentication API endpoints.
"""

from fastapi import APIRouter, HTTPException, status, Depends, Query
from fastapi.security import HTTPBearer
from typing import Optional
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend.models.schemas import LoginRequest, LoginResponse, UserInfo
from backend.core.security import create_access_token, generate_session_id
from backend.core.dependencies import get_current_user
from lib.dashboard_manager import session_manager, user_manager
import logging

logger = logging.getLogger(__name__)

router = APIRouter()
security = HTTPBearer()


@router.post("/login", response_model=LoginResponse)
async def login(request: LoginRequest):
    """Authenticate user and return JWT token."""
    try:
        # Get user data
        user_data = user_manager.get_user(request.username)
        if not user_data:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid username or password"
            )
        
        # Verify password using the existing user_manager method
        # This handles both hashed (bcrypt) and plain text (legacy) passwords
        if not user_manager.verify_user_password(request.username, request.password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid username or password"
            )
        
        # Create new session (this automatically invalidates all existing sessions for the user)
        # create_session handles invalidating all active sessions before creating a new one
        session_id = generate_session_id()
        session_manager.create_session(request.username, session_id)
        
        # Create JWT token with session_id included for session validation
        access_token = create_access_token(data={
            "sub": request.username,
            "session_id": session_id
        })
        
        # Get user role
        role = user_manager.get_user_role(request.username)
        
        return LoginResponse(
            access_token=access_token,
            username=request.username,
            role=role,
            session_id=session_id
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Login error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Login failed"
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
async def check_session(
    current_user: dict = Depends(get_current_user),
    session_id: Optional[str] = Query(None, description="Session ID to validate")
):
    """Check if session is valid.
    
    Args:
        session_id: Optional session ID to validate. If provided, validates the specific session.
                   If None, checks if any active session exists (for backwards compatibility).
    """
    username = current_user["username"]
    
    # If session_id provided, validate that specific session
    if session_id:
        is_valid = session_manager.validate_session(username, session_id)
        return {
            "valid": is_valid,
            "username": username
        }
    
    # Fallback: check if any active session exists (for backwards compatibility)
    existing_session = session_manager.check_existing_session(username)
    if existing_session:
        is_valid = session_manager.validate_session(username, existing_session)
        return {
            "valid": is_valid,
            "username": username
        }
    
    return {
        "valid": False,
        "username": username
    }

