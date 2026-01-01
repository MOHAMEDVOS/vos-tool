"""
Dashboard API endpoints.
"""

from fastapi import APIRouter, HTTPException, status, Depends, Query
from typing import Optional, List
from datetime import date, datetime
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend.models.schemas import AuditRecord, DashboardData, AuditFilter
from backend.core.dependencies import get_current_user
from backend.services.dashboard_service import (
    get_agent_audits,
    get_lite_audits,
    get_campaign_audits,
    clear_agent_audits,
    clear_lite_audits,
    clear_campaign_audits,
    get_available_campaigns
)
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/agent-audits", response_model=DashboardData)
async def get_agent_audit_data(
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    agent_name: Optional[str] = Query(None),
    current_user: dict = Depends(get_current_user)
):
    """Get agent audit data."""
    try:
        records = get_agent_audits(
            current_user["username"],
            start_date,
            end_date,
            agent_name
        )
        
        # Convert to AuditRecord format
        audit_records = []
        for record in records:
            audit_records.append(AuditRecord(
                id=str(record.get("id", "")),
                timestamp=record.get("timestamp", datetime.now()),
                agent_name=record.get("agent_name"),
                transcript=record.get("transcript"),
                rebuttals=record.get("rebuttals"),
                metadata=record
            ))
        
        return DashboardData(
            records=audit_records,
            total_count=len(audit_records),
            filters=AuditFilter(
                start_date=start_date,
                end_date=end_date,
                agent_name=agent_name
            ) if any([start_date, end_date, agent_name]) else None
        )
    except Exception as e:
        logger.error(f"Error getting agent audits: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load agent audit data"
        )


@router.get("/lite-audits", response_model=DashboardData)
async def get_lite_audit_data(
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    current_user: dict = Depends(get_current_user)
):
    """Get lite audit data."""
    try:
        records = get_lite_audits(
            current_user["username"],
            start_date,
            end_date
        )
        
        audit_records = []
        for record in records:
            audit_records.append(AuditRecord(
                id=str(record.get("id", "")),
                timestamp=record.get("timestamp", datetime.now()),
                transcript=record.get("transcript"),
                rebuttals=record.get("rebuttals"),
                metadata=record
            ))
        
        return DashboardData(
            records=audit_records,
            total_count=len(audit_records),
            filters=AuditFilter(
                start_date=start_date,
                end_date=end_date
            ) if any([start_date, end_date]) else None
        )
    except Exception as e:
        logger.error(f"Error getting lite audits: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load lite audit data"
        )


@router.get("/campaign-audits", response_model=DashboardData)
async def get_campaign_audit_data(
    campaign: Optional[str] = Query(None),
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    current_user: dict = Depends(get_current_user)
):
    """Get campaign audit data."""
    try:
        records = get_campaign_audits(
            current_user["username"],
            campaign,
            start_date,
            end_date
        )
        
        audit_records = []
        for record in records:
            audit_records.append(AuditRecord(
                id=str(record.get("id", "")),
                timestamp=record.get("timestamp", datetime.now()),
                campaign=record.get("campaign"),
                transcript=record.get("transcript"),
                rebuttals=record.get("rebuttals"),
                metadata=record
            ))
        
        return DashboardData(
            records=audit_records,
            total_count=len(audit_records),
            filters=AuditFilter(
                start_date=start_date,
                end_date=end_date,
                campaign=campaign
            ) if any([start_date, end_date, campaign]) else None
        )
    except Exception as e:
        logger.error(f"Error getting campaign audits: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load campaign audit data"
        )


@router.get("/campaigns", response_model=List[str])
async def get_campaigns_list(current_user: dict = Depends(get_current_user)):
    """Get list of available campaigns."""
    try:
        return get_available_campaigns(current_user["username"])
    except Exception as e:
        logger.error(f"Error getting campaigns: {e}", exc_info=True)
        return []


@router.post("/clear/agent-audits")
async def clear_agent_audit_data(current_user: dict = Depends(get_current_user)):
    """Clear all agent audit data."""
    try:
        success = clear_agent_audits(current_user["username"])
        if success:
            return {"message": "Agent audit data cleared successfully"}
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to clear agent audit data"
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error clearing agent audits: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to clear agent audit data"
        )


@router.post("/clear/lite-audits")
async def clear_lite_audit_data(current_user: dict = Depends(get_current_user)):
    """Clear all lite audit data."""
    try:
        success = clear_lite_audits(current_user["username"])
        if success:
            return {"message": "Lite audit data cleared successfully"}
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to clear lite audit data"
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error clearing lite audits: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to clear lite audit data"
        )


@router.post("/clear/campaign-audits")
async def clear_campaign_audit_data(
    campaign: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """Clear campaign audit data."""
    try:
        success = clear_campaign_audits(current_user["username"], campaign)
        if success:
            return {"message": "Campaign audit data cleared successfully"}
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to clear campaign audit data"
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error clearing campaign audits: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to clear campaign audit data"
        )

