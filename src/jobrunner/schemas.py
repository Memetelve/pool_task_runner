"""Pydantic schemas for request and response bodies."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator

from .models import JobStatus, UserRole


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TokenPayload(BaseModel):
    sub: UUID
    role: UserRole


class UserBase(BaseModel):
    email: EmailStr
    role: UserRole = UserRole.operator


class UserCreate(UserBase):
    password: str = Field(min_length=8)


class UserRead(UserBase):
    id: UUID
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class JobBase(BaseModel):
    name: str
    payload: dict[str, Any] = Field(default_factory=dict)
    queue: str | None = None
    priority: int = Field(default=5, ge=0, le=10)
    command: list[str] = Field(min_length=1)
    working_dir: str | None = None
    env: dict[str, str] | None = None


class JobCreate(JobBase):
    scheduled_at: datetime | None = None
    batch_id: UUID | None = None


class JobRead(JobBase):
    id: UUID
    status: JobStatus
    result: dict[str, Any] | None = None
    error: str | None = None
    scheduled_at: datetime | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime
    owner_id: UUID
    batch_id: UUID | None = None

    class Config:
        from_attributes = True


class JobList(BaseModel):
    items: list[JobRead]
    total: int


class JobStats(BaseModel):
    pending: int = 0
    running: int = 0
    success: int = 0
    failed: int = 0
    canceled: int = 0
    total: int = 0


class JobLogs(BaseModel):
    id: UUID
    stdout: str
    stderr: str
    return_code: int | None = None
    command: list[str] = Field(default_factory=list)
    working_dir: str | None = None


class JobBatchBase(BaseModel):
    name: str
    description: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)


class JobBatchCreate(JobBatchBase):
    jobs: list[JobCreate] = Field(min_items=1)


class JobBatchRead(JobBatchBase):
    id: UUID
    owner_id: UUID
    total_jobs: int
    pending_count: int
    running_count: int
    success_count: int
    failed_count: int
    canceled_count: int
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None

    class Config:
        from_attributes = True


class JobBatchDetail(JobBatchRead):
    jobs: list[JobRead]


class JobBatchList(BaseModel):
    items: list[JobBatchRead]
    total: int


class ForceCompleteRequest(BaseModel):
    status: JobStatus = JobStatus.success
    stdout: str | None = None
    stderr: str | None = None

    @field_validator("status")
    @classmethod
    def ensure_terminal(cls, value: JobStatus) -> JobStatus:
        if value in {JobStatus.pending, JobStatus.running}:
            raise ValueError("Force-complete status must be terminal")
        return value


class JobForceCompleteRequest(ForceCompleteRequest):
    pass


class BatchForceCompleteRequest(ForceCompleteRequest):
    pass


class HealthResponse(BaseModel):
    status: str
    redis: str
    database: str


class Message(BaseModel):
    detail: str
