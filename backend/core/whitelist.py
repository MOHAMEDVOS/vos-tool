import logging
from typing import Optional, Dict, Any
from backend.core.database import get_db

logger = logging.getLogger(__name__)

async def get_user_from_whitelist(email: str) -> Optional[Dict[str, Any]]:
    """
    Check if email is in the authorized database whitelist table.
    Returns user data (role, name, etc.) if found, else None.
    """
    db = get_db()
    if not db:
        logger.error("Database manager not available for whitelist check")
        return None
        
    try:
        query = "SELECT email, name, role, readymode_user, readymode_password FROM whitelist WHERE LOWER(email) = LOWER(%s)"
        user_data = db.execute_query(query, (email,), fetchone=True)
        
        if user_data:
            return {
                "email": user_data["email"],
                "name": user_data.get("name", ""),
                "role": user_data.get("role", "Auditor"),
                "readymode_user": user_data.get("readymode_user", ""),
                "readymode_password": user_data.get("readymode_password", "")
            }
        
        return None
        
    except Exception as e:
        logger.error(f"Error fetching whitelist from database: {e}")
        return None
