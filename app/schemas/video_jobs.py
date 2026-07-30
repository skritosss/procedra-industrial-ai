from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


VideoJobStatus = Literal["queued", "running", "succeeded", "failed", "cancelled"]


class VideoJobResponse(BaseModel):
    job_id: str = Field(..., min_length=32, max_length=32)
    status: VideoJobStatus
    stage: str = Field(..., min_length=1, max_length=50)
    progress_percent: int = Field(..., ge=0, le=100)
    attempts: int = Field(..., ge=0)
    max_attempts: int = Field(..., ge=1, le=10)
    cancel_requested: bool = False
    result_available: bool = False
    error_code: str | None = Field(default=None, max_length=50)
    error_message: str | None = Field(default=None, max_length=300)
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    updated_at: datetime

