"""Admin and Owner access to TL Actions reconciliation."""

from datetime import date, datetime
from html import escape
import logging

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from googleapiclient.errors import HttpError
from pydantic import BaseModel, Field, PositiveInt

from backend.core.dependencies import get_current_user
from backend.services import podio_integration
from backend.services.tl_actions_reconciliation import reconcile_tl_actions
from backend.services.tl_actions_submission import prepare_missing_action
from backend.services.tl_actions_tracker import append_missing_actions

router = APIRouter()
logger = logging.getLogger(__name__)


class ReconcileRequest(BaseModel):
    start_date: date
    end_date: date


class SubmitActionRequest(BaseModel):
    sheet_row: PositiveInt
    action_date: date
    details: str = Field(min_length=1, max_length=20000)
    started_after: datetime | None = None


class TrackerAction(BaseModel):
    action_date: date
    team_leader: str = Field(min_length=1, max_length=500)
    details: str = Field(min_length=1, max_length=20000)


class TrackerAppendRequest(BaseModel):
    start_date: date
    end_date: date
    actions: list[TrackerAction] = Field(min_length=1, max_length=2000)


def _require_admin(current_user: dict) -> None:
    if current_user.get("role") not in {"Admin", "Owner"}:
        raise HTTPException(status_code=403, detail="Admin or Owner access required")


def _require_owner(current_user: dict) -> None:
    if current_user.get("role") != "Owner":
        raise HTTPException(status_code=403, detail="Owner access required")


@router.post("/tracker/append")
def append_actions_to_tracker(
    body: TrackerAppendRequest,
    current_user: dict = Depends(get_current_user),
):
    _require_owner(current_user)
    if body.end_date < body.start_date:
        raise HTTPException(status_code=400, detail="End date must be on or after start date")
    try:
        return append_missing_actions(
            [action.model_dump() for action in body.actions],
            body.start_date,
            body.end_date,
        )
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except HttpError as exc:
        if exc.resp.status == 403:
            raise HTTPException(status_code=503, detail="Share the tracker spreadsheet with the backend service account as Editor") from exc
        logger.exception("Google Sheets rejected the TL actions tracker request")
        raise HTTPException(status_code=502, detail="Could not access the tracker spreadsheet") from exc
    except Exception as exc:
        logger.exception("Could not append TL actions to the tracker")
        raise HTTPException(status_code=502, detail="Could not save actions to the tracker sheet") from exc


@router.post("/reconcile")
def reconcile_actions(
    body: ReconcileRequest,
    current_user: dict = Depends(get_current_user),
):
    _require_admin(current_user)
    try:
        return reconcile_tl_actions(body.start_date, body.end_date)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Could not reconcile Actions sheet with Payroll") from exc


@router.post("/prepare")
def prepare_action(
    body: SubmitActionRequest,
    current_user: dict = Depends(get_current_user),
):
    _require_admin(current_user)
    try:
        return prepare_missing_action(
            row_number=body.sheet_row,
            action_date=body.action_date,
            expected_details=body.details,
            user_email=str(current_user.get("username", "")),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Could not prepare both action forms") from exc


@router.get("/podio/status")
def podio_status(current_user: dict = Depends(get_current_user)):
    _require_admin(current_user)
    return podio_integration.status()


@router.get("/podio/connect")
def podio_connect(current_user: dict = Depends(get_current_user)):
    _require_owner(current_user)
    try:
        return {"auth_url": podio_integration.create_authorization_url(current_user["username"])}
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Could not start Podio connection") from exc


@router.get("/podio/callback", response_class=HTMLResponse)
def podio_callback(code: str | None = None, state: str | None = None, error: str | None = None):
    if error or not code or not state:
        reason = "Podio authorization was cancelled or did not include a code. Close this window and try again."
        return HTMLResponse(f"<h2>{reason}</h2>", status_code=400)
    try:
        podio_integration.complete_authorization(code, state)
    except (ValueError, RuntimeError) as exc:
        message = escape(str(exc))
        logger.warning("Podio OAuth callback could not complete: %s", message)
        return HTMLResponse(f"<h2>Podio connection failed: {message}</h2><p>Close this window and fix the setting shown, then connect again.</p>", status_code=400)
    except Exception as exc:
        logger.error("Podio OAuth callback failed unexpectedly (%s)", type(exc).__name__)
        return HTMLResponse("<h2>Podio connection could not be saved. Check the backend logs, then try again.</h2>", status_code=500)
    origin = podio_integration.callback_origin()
    return HTMLResponse(
        "<!doctype html><meta charset='utf-8'><title>Podio connected</title>"
        "<p>Podio connected. This window can be closed.</p>"
        f"<script>window.opener?.postMessage({{type:'vos-podio-connected'}},{origin!r});window.close();</script>"
    )


@router.post("/podio/check")
def check_podio_action(body: SubmitActionRequest, current_user: dict = Depends(get_current_user)):
    _require_admin(current_user)
    try:
        item_id = podio_integration.find_submitted_action(body.action_date, body.details, body.started_after)
        return {"confirmed": item_id is not None, "item_id": item_id}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Could not check Podio for this action") from exc
