"""
Campaign AI report service.

Wraps lib.campaign_report_generator so the Streamlit UI no longer needs to
import it directly (gap G2).
"""

import sys
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import date
import logging

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from lib.campaign_report_generator import get_report_generator
from lib.dashboard_manager import dashboard_manager

logger = logging.getLogger(__name__)


def generate_campaign_report(
    campaign_name: str,
    username: str,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
) -> Dict[str, Any]:
    """Load the campaign's audit data and pass it to the LLM report generator.

    Returns {"success": bool, "report": str | None, "message": str | None,
             "campaign": str, "row_count": int}.
    """
    try:
        df = dashboard_manager.load_campaign_audit_data(
            campaign_name, start_date, end_date, username
        )
        if df is None or df.empty:
            return {
                "success": False,
                "report": None,
                "message": f"No audit data for campaign '{campaign_name}'",
                "campaign": campaign_name,
                "row_count": 0,
            }

        generator = get_report_generator()
        report = generator.generate_report(df, campaign_name)
        return {
            "success": True,
            "report": report,
            "message": None,
            "campaign": campaign_name,
            "row_count": int(len(df)),
        }
    except ValueError as e:
        # Raised when GROQ_API_KEY is missing
        logger.error(f"Campaign report config error: {e}")
        return {
            "success": False,
            "report": None,
            "message": str(e),
            "campaign": campaign_name,
            "row_count": 0,
        }
    except Exception as e:
        logger.error(f"Campaign report generation failed: {e}", exc_info=True)
        return {
            "success": False,
            "report": None,
            "message": f"Report generation failed: {e}",
            "campaign": campaign_name,
            "row_count": 0,
        }
