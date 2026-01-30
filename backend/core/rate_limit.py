"""
Rate limiting configuration for VOS Backend API.
Prevents resource exhaustion by limiting requests per user.
"""

from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from fastapi import Request, Response
from fastapi.responses import JSONResponse
import logging

logger = logging.getLogger(__name__)

# Initialize rate limiter
# Key function extracts client identifier (IP address by default)
# Can be customized to use user_id from JWT token for authenticated endpoints
limiter = Limiter(key_func=get_remote_address)


async def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> Response:
    """
    Custom handler for rate limit exceeded errors.
    Returns 429 status with helpful message.
    """
    logger.warning(
        f"Rate limit exceeded for {get_remote_address(request)} on {request.url.path}"
    )
    return JSONResponse(
        status_code=429,
        content={
            "error": "rate_limit_exceeded",
            "message": "Too many requests. Please wait before trying again.",
            "detail": str(exc.detail) if hasattr(exc, 'detail') else "Rate limit exceeded"
        }
    )


def get_user_id_from_token(request: Request) -> str:
    """
    Extract user ID from JWT token for per-user rate limiting.
    Falls back to IP address if token not present or invalid.
    """
    try:
        # Try to get user_id from request state (set by auth middleware)
        if hasattr(request.state, 'user') and request.state.user:
            return str(request.state.user.get('user_id', get_remote_address(request)))
        
        # Fallback to IP address
        return get_remote_address(request)
    except Exception as e:
        logger.debug(f"Could not extract user_id from token: {e}")
        return get_remote_address(request)


# Alternative limiter that uses user_id instead of IP
# Use this for authenticated endpoints to get true per-user limiting
user_limiter = Limiter(key_func=get_user_id_from_token)
