from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field, field_validator

from app.schemas.instruction import (
    EvidenceClaim,
    GenerationMode,
    InstructionLifecycleStatus,
    InstructionResponse,
    RiskLevel,
    normalize_generation_mode,
)


ReviewerRole = Literal["master", "technologist", "safety", "quality", "admin"]
__all_generation_mode__ = GenerationMode  # re-exported: storage and API share one vocabulary
AuditEventType = Literal[
    "version_saved",
    "workflow_updated",
    "claim_validated",
    "execution_saved",
]
ReviewText = Annotated[str, Field(min_length=1, max_length=500)]


class InstructionAuditEvent(BaseModel):
    event_id: str
    created_at: datetime
    event_type: AuditEventType
    actor: str = Field(..., min_length=1, max_length=120)
    reviewer_role: ReviewerRole | None = None
    from_status: InstructionLifecycleStatus | None = None
    to_status: InstructionLifecycleStatus | None = None
    comment: str | None = Field(default=None, max_length=1000)
    metadata: dict[str, str | int | float | bool] = Field(default_factory=dict)


class InstructionHistoryRecord(BaseModel):
    instruction_id: str
    organization_id: str = Field(default="legacy", min_length=1, max_length=64)
    project_id: str = Field(default="legacy", min_length=1, max_length=64)
    owner_user_id: str | None = Field(default=None, max_length=64)
    version: int = Field(..., ge=1)
    title: str
    created_at: datetime
    generation_mode: GenerationMode

    @field_validator("generation_mode", mode="before")
    @classmethod
    def accept_legacy_generation_mode(cls, value: object) -> object:
        return normalize_generation_mode(value)
    overall_score: int = Field(..., ge=0, le=100)
    risk_level: RiskLevel
    workflow_status: InstructionLifecycleStatus
    workflow_status_label: str
    reviewer: str | None = None
    reviewer_role: ReviewerRole | None = None
    review_comment: str | None = None
    reviewed_at: datetime | None = None
    resolved_blockers: list[ReviewText] = Field(default_factory=list, max_length=20)
    source_count: int = Field(..., ge=0)
    step_count: int = Field(..., ge=0)


class InstructionHistoryList(BaseModel):
    records: list[InstructionHistoryRecord] = Field(default_factory=list)


class SaveInstructionHistoryRequest(BaseModel):
    payload: InstructionResponse


class SaveInstructionHistoryResponse(BaseModel):
    record: InstructionHistoryRecord
    message: str


class InstructionHistoryDetail(BaseModel):
    record: InstructionHistoryRecord
    payload: InstructionResponse
    audit_events: list[InstructionAuditEvent] = Field(default_factory=list)


class InstructionAuditTrail(BaseModel):
    events: list[InstructionAuditEvent] = Field(default_factory=list)


class UpdateInstructionWorkflowRequest(BaseModel):
    status: InstructionLifecycleStatus
    reviewer: str = Field(..., min_length=2, max_length=120)
    reviewer_role: ReviewerRole
    comment: str = Field(..., min_length=5, max_length=1000)
    resolved_blockers: list[ReviewText] = Field(default_factory=list, max_length=20)


class UpdateInstructionWorkflowResponse(BaseModel):
    record: InstructionHistoryRecord
    message: str


class ValidateInstructionClaimRequest(BaseModel):
    evidence_reference: str = Field(..., min_length=3, max_length=500)
    evidence_sha256: str = Field(..., pattern=r"^[a-f0-9]{64}$")
    comment: str = Field(..., min_length=5, max_length=1000)


class ValidateInstructionClaimResponse(BaseModel):
    claim: EvidenceClaim
    message: str


class InstructionExecutionItem(BaseModel):
    label: str = Field(..., min_length=1, max_length=500)
    completed: bool = False


class SaveInstructionExecutionRequest(BaseModel):
    executor: str = Field(..., min_length=2, max_length=120)
    notes: str = Field(default="", max_length=2000)
    steps: list[InstructionExecutionItem] = Field(default_factory=list, min_length=1, max_length=64)
    quality_items: list[InstructionExecutionItem] = Field(default_factory=list, max_length=64)


class InstructionExecutionRecord(BaseModel):
    run_id: str
    instruction_id: str
    organization_id: str = Field(default="legacy", min_length=1, max_length=64)
    project_id: str = Field(default="legacy", min_length=1, max_length=64)
    owner_user_id: str | None = Field(default=None, max_length=64)
    version: int = Field(..., ge=1)
    created_at: datetime
    executor: str
    notes: str = ""
    completed_steps: int = Field(..., ge=0)
    total_steps: int = Field(..., ge=0)
    completed_quality_items: int = Field(..., ge=0)
    total_quality_items: int = Field(..., ge=0)


class InstructionExecutionDetail(BaseModel):
    record: InstructionExecutionRecord
    steps: list[InstructionExecutionItem] = Field(default_factory=list)
    quality_items: list[InstructionExecutionItem] = Field(default_factory=list)


class InstructionExecutionList(BaseModel):
    records: list[InstructionExecutionRecord] = Field(default_factory=list)


class SaveInstructionExecutionResponse(BaseModel):
    record: InstructionExecutionRecord
    message: str


class InstructionExecutionSummary(BaseModel):
    total_runs: int = Field(..., ge=0)
    total_steps: int = Field(..., ge=0)
    completed_steps: int = Field(..., ge=0)
    total_quality_items: int = Field(..., ge=0)
    completed_quality_items: int = Field(..., ge=0)
    step_completion_rate: float = Field(..., ge=0, le=100)
    quality_completion_rate: float = Field(..., ge=0, le=100)
    latest_runs: list[InstructionExecutionRecord] = Field(default_factory=list)
