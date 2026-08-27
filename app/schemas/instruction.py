from datetime import datetime
from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.schemas.video import FrameAnalysis, Keyframe, VideoSegment


UserLevel = Literal["new_operator", "experienced_operator", "engineer"]
IndustryProfile = Literal[
    "manufacturing",
    "construction",
    "occupational_safety",
    "emergency_response",
    "public_service",
    "housing_utilities",
    "healthcare",
    "education",
    "food_production",
    "transport",
    "information_security",
    "general",
]
InstructionType = Literal[
    "workplace_preparation",
    "equipment_startup",
    "equipment_shutdown",
    "inspection",
    "training",
    "maintenance",
    "general",
]
EvaluationCriterion = Literal[
    "completeness",
    "clarity",
    "input_alignment",
    "request_focus",
    "safety",
    "logical_sequence",
    "training_value",
    "source_grounding",
    "domain_risk_control",
    "implementation_readiness",
    "executability",
    "regulatory_structure",
]
InstructionLifecycleStatus = Literal["ai_draft", "expert_review", "approved", "rejected"]
RiskLevel = Literal["low", "medium", "high", "critical"]
EvidenceProvenance = Literal[
    "user_claim",
    "retrieved_unverified",
    "validated_local",
    "model_inference",
]
EvidenceValidationStatus = Literal["unverified", "validated"]
SafetyFindingCode = Literal[
    "hazardous_action",
    "contradictory_context",
    "unsupported_numeric_claim",
    "instruction_override",
]
EvidenceSourceType = Literal["user_input", "retrieved_source", "model_output"]
EvidenceValidatorRole = Literal["technologist", "safety", "quality", "admin"]


class ClaimValidationRecord(BaseModel):
    validation_id: str = Field(..., min_length=16, max_length=64)
    claim_id: str = Field(..., min_length=16, max_length=64)
    evidence_reference: str = Field(..., min_length=3, max_length=500)
    evidence_sha256: str = Field(..., pattern=r"^[a-f0-9]{64}$")
    reviewer_user_id: str = Field(..., min_length=1, max_length=64)
    reviewer_name: str = Field(..., min_length=2, max_length=120)
    reviewer_role: EvidenceValidatorRole
    comment: str = Field(..., min_length=5, max_length=1000)
    validated_at: datetime

    model_config = ConfigDict(str_strip_whitespace=True)


class EvidenceClaim(BaseModel):
    claim_id: str | None = Field(default=None, min_length=16, max_length=64)
    text: str = Field(..., min_length=1, max_length=500)
    provenance: EvidenceProvenance
    source_id: str | None = Field(default=None, min_length=1, max_length=128)
    source_type: EvidenceSourceType | None = None
    validation_status: EvidenceValidationStatus = "unverified"
    requires_local_verification: bool = True
    validation_record: ClaimValidationRecord | None = None

    model_config = ConfigDict(str_strip_whitespace=True)

    @model_validator(mode="after")
    def validate_local_evidence_contract(self):
        validated = self.validation_status == "validated"
        if validated != (self.provenance == "validated_local"):
            raise ValueError("validated claims must use validated_local provenance")
        if validated != (self.validation_record is not None):
            raise ValueError("validated claims require a validation record")
        if self.validation_record is not None and self.validation_record.claim_id != self.claim_id:
            raise ValueError("validation record must reference the same claim_id")
        if validated and self.requires_local_verification:
            raise ValueError("validated claims cannot require local verification")
        return self


class SafetyFinding(BaseModel):
    code: SafetyFindingCode
    severity: Literal["high", "critical"]
    message: str = Field(..., min_length=1, max_length=500)
    evidence_excerpt: str = Field(..., min_length=1, max_length=300)

    model_config = ConfigDict(str_strip_whitespace=True)


class InstructionWorkflow(BaseModel):
    status: InstructionLifecycleStatus = "ai_draft"
    status_label: str = "AI-черновик"
    required_review_roles: list[str] = Field(
        default_factory=lambda: [
            "Мастер смены или руководитель участка",
            "Инженер/технолог",
            "Специалист по охране труда",
        ],
        min_length=1,
    )
    approval_blockers: list[str] = Field(
        default_factory=lambda: [
            "Не подтверждены локальные режимы, допуски, нормы времени и применимые документы.",
            "Не проведена экспертная проверка применимости инструкции к конкретному участку и оборудованию.",
        ],
        min_length=1,
    )
    next_actions: list[str] = Field(
        default_factory=lambda: [
            "Передать AI-черновик ответственным специалистам на проверку.",
            "Заполнить отсутствующие локальные параметры и ссылки на действующие документы предприятия.",
            "После правок зафиксировать утвержденную версию в принятой системе документооборота.",
        ],
        min_length=1,
    )

    model_config = ConfigDict(str_strip_whitespace=True)

    @field_validator("required_review_roles", "approval_blockers", "next_actions", mode="before")
    @classmethod
    def clean_workflow_string_list(cls, value):
        return _clean_string_list(value)


class InstructionRequest(BaseModel):
    task: str = Field(..., min_length=10, max_length=2000)
    user_level: UserLevel = "new_operator"
    instruction_type: InstructionType = "general"
    department: str | None = Field(default=None, max_length=200)
    equipment: str | None = Field(default=None, max_length=200)
    operation_name: str | None = Field(default=None, max_length=200)
    industry_profile: IndustryProfile = "general"
    technical_context: str | None = Field(default=None, max_length=12000)

    model_config = ConfigDict(str_strip_whitespace=True)

    @field_validator("department", "equipment", "operation_name", "technical_context")
    @classmethod
    def empty_strings_to_none(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class InstructionStep(BaseModel):
    number: int = Field(..., ge=1)
    action: str = Field(..., min_length=1)
    expected_result: str = Field(..., min_length=1)
    safety_note: str | None = None
    verification_method: str | None = None
    common_mistakes: list[str] = Field(default_factory=list)

    model_config = ConfigDict(str_strip_whitespace=True)

    @field_validator("safety_note", "verification_method")
    @classmethod
    def empty_optional_strings_to_none(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None

    @field_validator("common_mistakes", mode="before")
    @classmethod
    def clean_optional_string_list(cls, value):
        return _clean_string_list(value)


class WorkInstruction(BaseModel):
    title: str = Field(..., min_length=1)
    purpose: str = Field(..., min_length=1)
    scope: str = Field(..., min_length=1)
    department: str | None = None
    equipment: str | None = None
    operator_level: str = Field(..., min_length=1)
    required_ppe: list[str] = Field(..., min_length=1)
    required_tools: list[str] = Field(..., min_length=1)
    safety_requirements: list[str] = Field(..., min_length=1)
    hazard_zones: list[str] = Field(..., min_length=1)
    prerequisites: list[str] = Field(..., min_length=1)
    steps: list[InstructionStep] = Field(..., min_length=1)
    control_points: list[str] = Field(..., min_length=1)
    quality_checklist: list[str] = Field(..., min_length=1)
    emergency_actions: list[str] = Field(..., min_length=1)
    common_mistakes: list[str] = Field(..., min_length=1)
    observed_facts: list[str] = Field(default_factory=list)
    evidence_claims: list[EvidenceClaim] = Field(default_factory=list, max_length=20)
    local_verification_required: list[str] = Field(default_factory=list)
    expert_review_questions: list[str] = Field(default_factory=list)
    workflow: InstructionWorkflow = Field(default_factory=InstructionWorkflow)

    model_config = ConfigDict(str_strip_whitespace=True)

    @field_validator("department", "equipment")
    @classmethod
    def empty_instruction_strings_to_none(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None

    @field_validator(
        "required_ppe",
        "required_tools",
        "safety_requirements",
        "hazard_zones",
        "prerequisites",
        "control_points",
        "quality_checklist",
        "emergency_actions",
        "common_mistakes",
        "observed_facts",
        "local_verification_required",
        "expert_review_questions",
        mode="before",
    )
    @classmethod
    def clean_required_string_list(cls, value):
        return _clean_string_list(value)

    @model_validator(mode="after")
    def validate_step_sequence(self):
        expected_numbers = list(range(1, len(self.steps) + 1))
        actual_numbers = [step.number for step in self.steps]
        if actual_numbers != expected_numbers:
            raise ValueError("Instruction steps must be numbered sequentially starting from 1")
        return self


class CriterionScore(BaseModel):
    criterion: EvaluationCriterion
    label: str
    score: int = Field(..., ge=0, le=100)
    strengths: list[str] = Field(default_factory=list)
    issues: list[str] = Field(default_factory=list)


class InstructionEvaluation(BaseModel):
    overall_score: int = Field(..., ge=0, le=100)
    criteria: list[CriterionScore] = Field(..., min_length=1)
    missing_elements: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    verdict: str
    risk_level: RiskLevel = "medium"
    expert_review_required: bool = True
    expert_review_notes: list[str] = Field(default_factory=list)
    safety_findings: list[SafetyFinding] = Field(default_factory=list)


class EvaluationRequest(BaseModel):
    instruction: WorkInstruction
    source_request: InstructionRequest | None = None


class InstructionPayloadRequest(BaseModel):
    payload: "InstructionResponse"
    source_request: InstructionRequest | None = None


class RetrievedSource(BaseModel):
    source_id: str
    title: str
    path: str
    chunk_index: int
    score: float = Field(..., ge=0)
    excerpt: str
    source_type: Literal["local", "public"] = "local"
    url: str | None = Field(default=None, max_length=1200)
    influence_score: float = Field(default=0.0, ge=0, le=1)
    matched_terms: list[str] = Field(default_factory=list)
    authority: str | None = Field(default=None, max_length=300)
    document_type: str | None = Field(default=None, max_length=200)
    applicable_profiles: list[IndustryProfile] = Field(default_factory=list, max_length=12)
    contribution_reason: str | None = Field(default=None, max_length=800)

    model_config = ConfigDict(str_strip_whitespace=True)

    @field_validator("url")
    @classmethod
    def validate_external_url(cls, value: str | None) -> str | None:
        if value is None:
            return None
        parsed = urlsplit(value)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("Source URL must use HTTP or HTTPS")
        return value

    @field_validator("authority", "document_type", "contribution_reason")
    @classmethod
    def empty_source_metadata_to_none(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None

    @field_validator("applicable_profiles")
    @classmethod
    def deduplicate_applicable_profiles(cls, value: list[IndustryProfile]) -> list[IndustryProfile]:
        return list(dict.fromkeys(value))


class ContextGenerationRequest(InstructionRequest):
    max_sources: int = Field(default=15, ge=1, le=15)


class VideoInstructionRequest(ContextGenerationRequest):
    technical_context: str | None = Field(default=None, max_length=50000)
    keyframes: list[Keyframe] = Field(default_factory=list, max_length=32)
    frame_analyses: list[FrameAnalysis] = Field(default_factory=list, max_length=32)
    video_segments: list[VideoSegment] = Field(default_factory=list, max_length=16)

    @model_validator(mode="after")
    def validate_video_frame_context(self):
        if not self.keyframes:
            raise ValueError("Video instruction generation requires at least one extracted keyframe")

        keyframe_indices = [keyframe.frame_index for keyframe in self.keyframes]
        if len(keyframe_indices) != len(set(keyframe_indices)):
            raise ValueError("Video keyframes must not contain duplicate frame_index values")

        timestamps_by_frame = {keyframe.frame_index: keyframe.timestamp_seconds for keyframe in self.keyframes}
        analysis_indices = [analysis.frame_index for analysis in self.frame_analyses]
        if len(analysis_indices) != len(set(analysis_indices)):
            raise ValueError("Frame analyses must not contain duplicate frame_index values")

        unknown_analysis_frames = sorted(set(analysis_indices) - set(timestamps_by_frame))
        if unknown_analysis_frames:
            raise ValueError("Frame analyses must reference an extracted keyframe")

        for analysis in self.frame_analyses:
            keyframe_timestamp = timestamps_by_frame[analysis.frame_index]
            if abs(analysis.timestamp_seconds - keyframe_timestamp) > 0.5:
                raise ValueError("Frame analysis timestamp must match the referenced keyframe timestamp")

        keyframe_set = set(timestamps_by_frame)
        segment_indices = [segment.segment_index for segment in self.video_segments]
        if len(segment_indices) != len(set(segment_indices)):
            raise ValueError("Video segments must not contain duplicate segment_index values")
        for segment in self.video_segments:
            unknown_segment_frames = sorted(set(segment.frame_indices) - keyframe_set)
            if unknown_segment_frames:
                raise ValueError("Video segments must reference extracted keyframes")
        return self


class StepFrameLink(BaseModel):
    step_number: int = Field(..., ge=1)
    frame_index: int = Field(..., ge=0)
    timestamp_seconds: float = Field(..., ge=0)
    reason: str = Field(..., min_length=1)
    confidence: float = Field(..., ge=0, le=1)
    image_url: str | None = None
    analysis_mode: str | None = None

    model_config = ConfigDict(str_strip_whitespace=True)

    @field_validator("image_url", "analysis_mode")
    @classmethod
    def empty_link_strings_to_none(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


GenerationMode = Literal["model", "deterministic"]

# Rows written before ADR-0001 carry the vendor name in the payload JSON. The
# value is not part of the audit hash and not part of the instruction id, so it
# is safe to translate — but it is validated on read, and narrowing the literal
# without this map would make every stored instruction unreadable.
LEGACY_GENERATION_MODES = {"openai": "model", "fallback": "deterministic"}


def normalize_generation_mode(value: object) -> object:
    if isinstance(value, str):
        return LEGACY_GENERATION_MODES.get(value, value)
    return value


class InstructionResponse(BaseModel):
    instruction: WorkInstruction
    markdown: str
    generation_mode: GenerationMode
    evaluation: InstructionEvaluation
    sources: list[RetrievedSource] = Field(default_factory=list, max_length=30)
    step_frame_links: list[StepFrameLink] = Field(default_factory=list, max_length=32)

    @field_validator("generation_mode", mode="before")
    @classmethod
    def accept_legacy_generation_mode(cls, value: object) -> object:
        return normalize_generation_mode(value)


def _clean_string_list(value):
    if value is None:
        return []
    if not isinstance(value, list):
        return value
    return [item.strip() for item in value if isinstance(item, str) and item.strip()]
