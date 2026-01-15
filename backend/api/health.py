"""
Health check API endpoints for database monitoring (Owner-only access).
"""

from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/health", tags=["health"])

# Import owner authentication dependency
from backend.core.dependencies import get_current_owner_user


@router.get("/database")
async def get_database_health(current_user: dict = Depends(get_current_owner_user)) -> Dict[str, Any]:
    """
    Get comprehensive database health status.
    
    Returns:
        Dictionary with health metrics, pool status, query stats, and alerts
    """
    try:
        from lib.db_health_monitor import get_health_monitor
        
        monitor = get_health_monitor()
        if not monitor:
            raise HTTPException(
                status_code=503,
                detail="Health monitor not available - database manager may not be initialized"
            )
        
        summary = monitor.get_health_summary()
        return summary
        
    except Exception as e:
        logger.error(f"Health check failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Health check error: {str(e)}")


@router.get("/database/pool")
async def get_pool_metrics(current_user: dict = Depends(get_current_owner_user)) -> Dict[str, Any]:
    """
    Get connection pool metrics.
    
    Returns:
        Dictionary with pool statistics
    """
    try:
        from lib.db_health_monitor import get_health_monitor
        
        monitor = get_health_monitor()
        if not monitor:
            raise HTTPException(
                status_code=503,
                detail="Health monitor not available"
            )
        
        return monitor.get_pool_metrics()
        
    except Exception as e:
        logger.error(f"Pool metrics check failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/database/queries")
async def get_query_metrics(current_user: dict = Depends(get_current_owner_user)) -> Dict[str, Any]:
    """
    Get query performance metrics.
    
    Returns:
        Dictionary with query statistics
    """
    try:
        from lib.db_health_monitor import get_health_monitor
        
        monitor = get_health_monitor()
        if not monitor:
            raise HTTPException(
                status_code=503,
                detail="Health monitor not available"
            )
        
        return monitor.get_query_metrics()
        
    except Exception as e:
        logger.error(f"Query metrics check failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/database/slow-queries")
async def get_slow_queries(limit: int = 10, current_user: dict = Depends(get_current_owner_user)) -> Dict[str, Any]:
    """
    Get recent slow queries.
    
    Args:
        limit: Maximum number of slow queries to return (default: 10)
    
    Returns:
        Dictionary with list of slow queries
    """
    try:
        from lib.db_health_monitor import get_health_monitor
        
        monitor = get_health_monitor()
        if not monitor:
            raise HTTPException(
                status_code=503,
                detail="Health monitor not available"
            )
        
        slow_queries = monitor.get_slow_queries(limit=limit)
        return {
            "count": len(slow_queries),
            "queries": slow_queries
        }
        
    except Exception as e:
        logger.error(f"Slow queries check failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/database/alerts")
async def get_health_alerts(current_user: dict = Depends(get_current_owner_user)) -> Dict[str, Any]:
    """
    Get active health alerts.
    
    Returns:
        Dictionary with list of active alerts
    """
    try:
        from lib.db_health_monitor import get_health_monitor
        
        monitor = get_health_monitor()
        if not monitor:
            raise HTTPException(
                status_code=503,
                detail="Health monitor not available"
            )
        
        alerts = monitor.get_alerts()
        return {
            "count": len(alerts),
            "alerts": [
                {
                    "level": alert.level,
                    "message": alert.message,
                    "timestamp": alert.timestamp,
                    "metric": alert.metric,
                    "value": alert.value
                }
                for alert in alerts
            ]
        }
        
    except Exception as e:
        logger.error(f"Alerts check failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/database/reset-metrics")
async def reset_metrics(current_user: dict = Depends(get_current_owner_user)) -> Dict[str, str]:
    """
    Reset health monitoring metrics.
    
    Returns:
        Success message
    """
    try:
        from lib.db_health_monitor import get_health_monitor
        
        monitor = get_health_monitor()
        if not monitor:
            raise HTTPException(
                status_code=503,
                detail="Health monitor not available"
            )
        
        monitor.reset_metrics()
        return {"message": "Metrics reset successfully"}
        
    except Exception as e:
        logger.error(f"Metrics reset failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
