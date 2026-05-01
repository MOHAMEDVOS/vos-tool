"""
Phrase management API endpoints (Owner-only).

Replaces the direct lib.phrase_learning imports in
frontend/app_ai/ui/phrases.py. Maps backend gaps G1 + G11 from the
Streamlit->React migration plan.
"""

import sys
from pathlib import Path
from typing import List, Dict, Any
import logging

from fastapi import APIRouter, Depends, HTTPException, status

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend.core.dependencies import get_current_owner_user
from backend.models.schemas import (
    PhraseStats,
    PendingPhrase,
    AddPhraseRequest,
    BulkAddPhrasesRequest,
    RejectPhraseRequest,
    ApproveByQualityRequest,
    ApproveByCategoryRequest,
    PhraseLearningSettings,
    GenericActionResponse,
)
from backend.services import phrase_service

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/stats", response_model=PhraseStats)
async def get_phrase_stats(_: dict = Depends(get_current_owner_user)):
    return PhraseStats(**phrase_service.get_stats())


@router.get("/")
async def list_phrases(_: dict = Depends(get_current_owner_user)) -> Dict[str, List[str]]:
    """Approved phrases grouped by category."""
    return phrase_service.get_all_phrases()


@router.get("/pending", response_model=List[PendingPhrase])
async def list_pending(
    status_filter: str = "pending",
    _: dict = Depends(get_current_owner_user),
):
    return phrase_service.get_pending(status=status_filter)


@router.post("/", response_model=GenericActionResponse)
async def add_phrase(
    req: AddPhraseRequest,
    _: dict = Depends(get_current_owner_user),
):
    result = phrase_service.add_phrase(req.phrase, req.category)
    if not result.get("success"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.get("message", "Failed to add phrase"),
        )
    return GenericActionResponse(success=True, message=result.get("message"))


@router.post("/bulk")
async def add_phrases_bulk(
    req: BulkAddPhrasesRequest,
    _: dict = Depends(get_current_owner_user),
) -> Dict[str, Any]:
    return phrase_service.add_phrases_bulk(req.phrases, req.category)


@router.post("/{phrase_id}/approve", response_model=GenericActionResponse)
async def approve_phrase(
    phrase_id: str,
    _: dict = Depends(get_current_owner_user),
):
    ok = phrase_service.approve(phrase_id)
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Phrase {phrase_id} not found or could not be approved",
        )
    return GenericActionResponse(success=True, message=f"Phrase {phrase_id} approved")


@router.post("/{phrase_id}/reject", response_model=GenericActionResponse)
async def reject_phrase(
    phrase_id: str,
    req: RejectPhraseRequest,
    _: dict = Depends(get_current_owner_user),
):
    ok = phrase_service.reject(phrase_id, req.reason)
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Phrase {phrase_id} not found or could not be rejected",
        )
    return GenericActionResponse(success=True, message=f"Phrase {phrase_id} rejected")


@router.post("/approve-all")
async def approve_all_pending(_: dict = Depends(get_current_owner_user)) -> Dict[str, Any]:
    return phrase_service.approve_all_pending()


@router.post("/approve-by-quality")
async def approve_by_quality(
    req: ApproveByQualityRequest,
    _: dict = Depends(get_current_owner_user),
) -> Dict[str, Any]:
    return phrase_service.approve_by_quality(req.min_quality_score)


@router.post("/approve-by-category")
async def approve_by_category(
    req: ApproveByCategoryRequest,
    _: dict = Depends(get_current_owner_user),
) -> Dict[str, Any]:
    return phrase_service.approve_by_category(req.category, req.min_quality_score)


@router.post("/remove-duplicates")
async def remove_duplicates(_: dict = Depends(get_current_owner_user)) -> Dict[str, Any]:
    return phrase_service.remove_duplicates()


@router.get("/settings", response_model=PhraseLearningSettings)
async def get_learning_settings(_: dict = Depends(get_current_owner_user)):
    return PhraseLearningSettings(**phrase_service.get_settings())


@router.put("/settings")
async def update_learning_settings(
    req: PhraseLearningSettings,
    _: dict = Depends(get_current_owner_user),
) -> Dict[str, Any]:
    return phrase_service.update_settings(
        confidence_threshold=req.confidence_threshold,
        frequency_threshold=req.frequency_threshold,
        auto_approve_threshold=req.auto_approve_threshold,
    )
