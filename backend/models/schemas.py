"""
Pydantic models for API request/response schemas.
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any, Union
from datetime import datetime, date


# Authentication schemas
class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    username: str
    name: Optional[str] = None
    picture: Optional[str] = None
    role: str
    session_id: str


class UserInfo(BaseModel):
    username: str
    role: str
    daily_limit: Optional[int] = None


# Audio processing schemas
class AudioUploadResponse(BaseModel):
    file_id: str
    filename: str
    message: str


class ProcessAudioRequest(BaseModel):
    file_id: str
    audit_type: str = "heavy"  # "heavy" or "lite"
    options: Optional[Dict[str, Any]] = None


class ProcessingStatus(BaseModel):
    job_id: str
    status: str  # "pending", "processing", "completed", "failed"
    progress: Optional[float] = None
    message: Optional[str] = None
    stage: Optional[str] = None  # Current processing stage (e.g., "queued", "processing_heavy_single", "transcribing")


class ProcessingResult(BaseModel):
    job_id: str
    status: str
    transcript: Optional[str] = None
    agent_transcript: Optional[str] = None
    customer_transcript: Optional[str] = None
    rebuttals: Optional[List[Dict[str, Any]]] = None
    accent_corrections: Optional[List[Dict[str, Any]]] = None
    metadata: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    # New transcription-specific fields for better error reporting
    transcription_status: Optional[str] = None  # "completed", "failed", "timeout"
    transcription_error: Optional[str] = None  # Specific transcription error details
    processing_stage: Optional[str] = None  # Current processing stage


# Dashboard schemas
class AuditFilter(BaseModel):
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    agent_name: Optional[str] = None
    campaign: Optional[str] = None


class AuditRecord(BaseModel):
    id: str
    timestamp: datetime
    agent_name: Optional[str] = None
    campaign: Optional[str] = None
    transcript: Optional[str] = None
    rebuttals: Optional[List[Dict[str, Any]]] = None
    metadata: Optional[Dict[str, Any]] = None


class DashboardData(BaseModel):
    records: List[AuditRecord]
    total_count: int
    filters: Optional[AuditFilter] = None


# Settings schemas
class UserSettings(BaseModel):
    daily_limit: Optional[int] = None
    readymode_username: Optional[str] = None
    readymode_password: Optional[str] = None
    assemblyai_api_key_encrypted: Optional[str] = Field(None, description="Encrypted AssemblyAI API key")
    preferences: Optional[Dict[str, Any]] = None


class CreateUserRequest(BaseModel):
    username: str
    password: Optional[str] = ""
    role: str = "Auditor"
    daily_limit: Optional[int] = None
    readymode_username: Optional[str] = None
    readymode_password: Optional[str] = None
    assemblyai_api_key_encrypted: Optional[str] = Field(None, description="Encrypted AssemblyAI API key")


class UpdateUserRequest(BaseModel):
    password: Optional[str] = None
    role: Optional[str] = None
    daily_limit: Optional[int] = None
    readymode_username: Optional[str] = None
    readymode_password: Optional[str] = None
    assemblyai_api_key_encrypted: Optional[str] = Field(None, description="Encrypted AssemblyAI API key")


class UserListResponse(BaseModel):
    users: List[UserInfo]
    total: int


# ReadyMode schemas
class ReadyModeDownloadRequest(BaseModel):
    dialer_url: Optional[str] = None
    agent_name: Optional[str] = None
    campaign_name: Optional[str] = None
    max_calls: Optional[int] = None
    start_date: Optional[str] = None   # ISO date string YYYY-MM-DD
    end_date: Optional[str] = None
    dispositions: Optional[List[str]] = None
    duration_filter: Optional[str] = None   # e.g. "all", "lt30", "30to60", "60to600", "gt_custom", "lt_custom"
    custom_duration_seconds: Optional[int] = None
    audit_type: Optional[str] = "heavy"  # "heavy" | "lite"


class ReadyModeStatus(BaseModel):
    status: str
    downloaded_count: Optional[int] = None
    analyzed_count: Optional[int] = None
    message: Optional[str] = None


# System health
class SystemHealth(BaseModel):
    cpu: float
    memory: float
    disk: float
    healthy: bool



# Phrase management schemas (G1, G11)
class PhraseStats(BaseModel):
    total_phrases: int
    pending_count: int
    auto_learned_count: int
    categories: int
    last_updated: str


class PendingPhrase(BaseModel):
    id: Union[int, str]
    phrase: str
    category: str
    confidence: Optional[float] = None
    detection_count: Optional[int] = None
    first_detected: Optional[datetime] = None
    last_detected: Optional[datetime] = None
    sample_contexts: Optional[str] = ""
    similar_to: Optional[str] = ""
    quality_score: Optional[float] = None
    canonical_form: Optional[str] = None
    quality_tier: Optional[str] = None


class AddPhraseRequest(BaseModel):
    phrase: str = Field(..., min_length=3)
    category: str = Field(..., min_length=1)


class BulkAddPhrasesRequest(BaseModel):
    phrases: List[str]
    category: str = Field(..., min_length=1)


class RejectPhraseRequest(BaseModel):
    reason: str = ""


class ApproveByQualityRequest(BaseModel):
    min_quality_score: float = Field(0.90, ge=0.0, le=1.0)


class ApproveByCategoryRequest(BaseModel):
    category: str
    min_quality_score: float = Field(0.80, ge=0.0, le=1.0)


class PhraseLearningSettings(BaseModel):
    confidence_threshold: Optional[float] = Field(None, ge=0.5, le=1.0)
    frequency_threshold: Optional[int] = Field(None, ge=1)
    auto_approve_threshold: Optional[float] = Field(None, ge=0.8, le=1.0)


class GenericActionResponse(BaseModel):
    success: bool
    message: Optional[str] = None


# Campaign AI report schemas (G2)
class CampaignReportRequest(BaseModel):
    start_date: Optional[date] = None
    end_date: Optional[date] = None


class CampaignReportResponse(BaseModel):
    success: bool
    campaign: str
    report: Optional[str] = None
    message: Optional[str] = None
    row_count: int = 0


# Quota schemas (G3, G4)
class QuotaAllocations(BaseModel):
    allocations: Dict[str, int]


class AdminLimitsRequest(BaseModel):
    admin_username: str
    max_users: int = Field(..., ge=0)
    daily_quota: int = Field(..., ge=0)


# Dashboard sharing schemas (G5)
class CreateSharingGroupRequest(BaseModel):
    group_name: str = Field(..., min_length=1)
    members: List[str] = Field(default_factory=list)


class UpdateSharingGroupRequest(BaseModel):
    members: List[str]
