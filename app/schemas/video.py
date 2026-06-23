from pydantic import BaseModel, Field, field_validator, model_validator


class Keyframe(BaseModel):
    frame_index: int = Field(..., ge=0)
    timestamp_seconds: float = Field(..., ge=0)
    image_path: str = Field(..., max_length=500)
    image_url: str = Field(..., max_length=500)
    selection_score: float = Field(default=0.0, ge=0, le=1)
    selection_reason: str = Field(default="", max_length=300)

    @field_validator("selection_reason")
    @classmethod
    def clean_selection_reason(cls, value: str) -> str:
        return value.strip()


class FrameAnalysis(BaseModel):
    frame_index: int = Field(..., ge=0)
    timestamp_seconds: float = Field(..., ge=0)
    summary: str = Field(..., min_length=1, max_length=1000)
    visible_equipment: list[str] = Field(default_factory=list, max_length=12)
    operator_actions: list[str] = Field(default_factory=list, max_length=12)
    safety_observations: list[str] = Field(default_factory=list, max_length=12)
    ppe_observations: list[str] = Field(default_factory=list, max_length=12)
    potential_hazards: list[str] = Field(default_factory=list, max_length=12)
    uncertainties: list[str] = Field(default_factory=list, max_length=12)
    analysis_mode: str = Field(default="fallback", max_length=50)

    @field_validator(
        "visible_equipment",
        "operator_actions",
        "safety_observations",
        "ppe_observations",
        "potential_hazards",
        "uncertainties",
        mode="before",
    )
    @classmethod
    def clean_string_lists(cls, value):
        if value is None:
            return []
        if not isinstance(value, list):
            return value
        return [item.strip()[:300] for item in value if isinstance(item, str) and item.strip()]


class VideoSegment(BaseModel):
    segment_index: int = Field(..., ge=1)
    start_seconds: float = Field(..., ge=0)
    end_seconds: float = Field(..., ge=0)
    frame_indices: list[int] = Field(default_factory=list, max_length=32)
    summary: str = Field(..., min_length=1, max_length=1000)
    dominant_actions: list[str] = Field(default_factory=list, max_length=12)
    visible_equipment: list[str] = Field(default_factory=list, max_length=12)
    safety_findings: list[str] = Field(default_factory=list, max_length=12)
    uncertainties: list[str] = Field(default_factory=list, max_length=12)

    @field_validator(
        "dominant_actions",
        "visible_equipment",
        "safety_findings",
        "uncertainties",
        mode="before",
    )
    @classmethod
    def clean_segment_string_lists(cls, value):
        if value is None:
            return []
        if not isinstance(value, list):
            return value
        return [item.strip()[:300] for item in value if isinstance(item, str) and item.strip()]

    @field_validator("frame_indices", mode="before")
    @classmethod
    def clean_frame_indices(cls, value):
        if value is None:
            return []
        if not isinstance(value, list):
            return value
        return [item for item in value if isinstance(item, int) and item >= 0]

    @model_validator(mode="after")
    def validate_time_range(self):
        if self.end_seconds < self.start_seconds:
            raise ValueError("Video segment end_seconds must be greater than or equal to start_seconds")
        return self


class VideoKeyframeResponse(BaseModel):
    video_id: str = Field(..., max_length=80)
    organization_id: str = Field(default="legacy", min_length=1, max_length=64)
    project_id: str = Field(default="legacy", min_length=1, max_length=64)
    owner_user_id: str | None = Field(default=None, max_length=64)
    original_filename: str = Field(..., max_length=300)
    source_url: str | None = Field(default=None, max_length=1000)
    frame_count: int = Field(..., ge=0)
    fps: float = Field(..., ge=0)
    duration_seconds: float = Field(..., ge=0)
    keyframes: list[Keyframe] = Field(default_factory=list)
    frame_analyses: list[FrameAnalysis] = Field(default_factory=list)
    video_segments: list[VideoSegment] = Field(default_factory=list)
    extracted_context: str = Field(default="", max_length=12000)
    transcript: str = Field(default="", max_length=6000)
    visual_quality: str = Field(default="local", max_length=20)
    notes: list[str] = Field(default_factory=list, max_length=20)
