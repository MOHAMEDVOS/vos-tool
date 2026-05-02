"""
Reports API — campaign report export to Google Sheets + Docs.
"""

import sys
from pathlib import Path
from typing import Optional
from datetime import date

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel
from backend.core.dependencies import get_current_user
from backend.services.campaign_report_export import generate_campaign_report
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


class GenerateReportRequest(BaseModel):
    campaign: str
    start_date: Optional[date] = None
    end_date: Optional[date] = None


@router.post("/campaign/generate")
async def generate_report(
    body: GenerateReportRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    Generate a Google Sheet + Doc for the selected campaign.
    Returns { sheet_url, doc_url }.
    Returns 401 with code "google_not_connected" if the user hasn't
    connected Google Workspace yet — frontend should trigger re-auth.
    """
    username = current_user["username"]
    try:
        result = generate_campaign_report(
            username=username,
            campaign_name=body.campaign,
            start_date=body.start_date,
            end_date=body.end_date,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Report generation failed for {username}/{body.campaign}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Report generation failed")
