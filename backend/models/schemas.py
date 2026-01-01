"""
Pydantic models for API request/response schemas.
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime, date


# Authentication schemas
class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    username: str
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
    password: str
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
    max_calls: Optional[int] = None


class ReadyModeStatus(BaseModel):
    status: str
    downloaded_count: Optional[int] = None
    message: Optional[str] = None


# System health
class SystemHealth(BaseModel):
    cpu: float
    memory: float
    disk: float
    healthy: bool

