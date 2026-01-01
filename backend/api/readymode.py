"""
ReadyMode API endpoints.
"""

from fastapi import APIRouter, HTTPException, status, Depends
from typing import Optional
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend.models.schemas import ReadyModeDownloadRequest, ReadyModeStatus
from backend.core.dependencies import get_current_user
from backend.core.config import settings
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/download", response_model=ReadyModeStatus)
async def download_readymode_calls(
    request: ReadyModeDownloadRequest,
    current_user: dict = Depends(get_current_user)
):
    """Download calls from ReadyMode."""
    if not settings.READYMODE_AVAILABLE:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="ReadyMode automation is not available"
        )
    
    try:
        # Import ReadyMode automation
        from automation.download_readymode_calls import (
            download_all_call_recordings,
            ReadyModeLoginError,
            ReadyModeNoCallsError
        )
        from config import get_user_readymode_credentials, get_user_daily_limit
        
        # Get user credentials
        readymode_user, readymode_pass = get_user_readymode_credentials(current_user["username"])
        if not readymode_user or not readymode_pass:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="ReadyMode credentials not configured for user"
            )
        
        # Get daily limit
        daily_limit = get_user_daily_limit(current_user["username"])
        
        # Download calls
        dialer_url = request.dialer_url or "https://resva.readymode.com/"
        max_calls = request.max_calls or daily_limit
        
        downloaded = download_all_call_recordings(
            readymode_user,
            readymode_pass,
            dialer_url,
            max_calls,
            current_user["username"]
        )
        
        return ReadyModeStatus(
            status="completed",
            downloaded_count=downloaded,
            message=f"Downloaded {downloaded} calls"
        )
    except ReadyModeLoginError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"ReadyMode login failed: {str(e)}"
        )
    except ReadyModeNoCallsError as e:
        return ReadyModeStatus(
            status="completed",
            downloaded_count=0,
            message=str(e)
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"ReadyMode download error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to download calls"
        )


@router.get("/status", response_model=ReadyModeStatus)
async def get_readymode_status(current_user: dict = Depends(get_current_user)):
    """Get ReadyMode status."""
    from config import get_user_readymode_credentials
    
    readymode_user, readymode_pass = get_user_readymode_credentials(current_user["username"])
    
    return ReadyModeStatus(
        status="available" if (readymode_user and readymode_pass) else "not_configured",
        message="ReadyMode configured" if (readymode_user and readymode_pass) else "ReadyMode credentials not set"
    )

