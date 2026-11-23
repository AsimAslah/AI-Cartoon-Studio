from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class VideoProviderState(str, Enum):
    AVAILABLE = "available"
    NOT_CONFIGURED = "not_configured"
    DEPENDENCY_MISSING = "dependency_missing"
    AUTHENTICATION_REQUIRED = "authentication_required"
    TEMPORARILY_UNAVAILABLE = "temporarily_unavailable"


class VideoJobState(str, Enum):
    QUEUED = "QUEUED"
    VALIDATING = "VALIDATING"
    UPLOADING = "UPLOADING"
    SUBMITTED = "SUBMITTED"
    PROVIDER_QUEUED = "PROVIDER_QUEUED"
    RUNNING = "RUNNING"
    DOWNLOADING = "DOWNLOADING"
    VERIFYING = "VERIFYING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class VideoProviderCapabilities(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider_id: str
    name: str
    model_id: str
    state: VideoProviderState
    configured: bool
    credentials_required: bool
    credentials_configured: bool
    remote_processing: bool = True
    may_consume_quota: bool = True
    may_incur_cost: bool = False
    space_id: str | None = None
    api_name: str | None = None
    supported_image_types: list[str]
    supported_durations: list[float]
    resolution_presets: dict[str, tuple[int, int]]
    supported_decoders: list[str]
    supports_seed: bool
    supports_prompt_enhancement: bool
    supports_negative_prompt: bool = False
    supports_audio_toggle: bool = False
    note: str


class VideoImageRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0"] = "1.0"
    upload_id: UUID
    created_at: datetime
    original_filename: str
    stored_filename: str
    content_type: str
    bytes: int = Field(gt=0)


class VideoImageResponse(VideoImageRecord):
    preview_url: str


class VideoGenerationSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    duration_seconds: float = Field(default=3.0, ge=1.0, le=5.0)
    width: int = Field(default=1024, ge=512, le=1536)
    height: int = Field(default=576, ge=512, le=1536)
    seed: int = Field(default=0, ge=0, le=2_147_483_647)
    decoder: Literal["diffusion", "conv"] = "diffusion"
    auto_length: bool = False
    randomize_seed: bool = True
    enhance_prompt: bool = False

    @model_validator(mode="after")
    def dimensions_match_provider_grid(self) -> "VideoGenerationSettings":
        if self.width % 64 or self.height % 64:
            raise ValueError("Video width and height must be divisible by 64.")
        return self


class VideoGenerationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    upload_id: UUID
    provider_id: Literal["huggingface_ltx_2_5"] = "huggingface_ltx_2_5"
    prompt: str = Field(min_length=10, max_length=4_000)
    settings: VideoGenerationSettings = Field(default_factory=VideoGenerationSettings)
    remote_processing_consent: Literal[True]

    @field_validator("prompt")
    @classmethod
    def normalize_prompt(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 10:
            raise ValueError("Animation prompt must contain at least 10 characters.")
        return value


class VideoMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    width: int = Field(gt=0)
    height: int = Field(gt=0)
    duration_seconds: float = Field(gt=0)
    frame_rate: float = Field(gt=0)
    codec: str


class VideoProviderResult(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    provider_job_id: str | None = None
    output_path: str
    effective_prompt: str
    effective_seed: int


class VideoJobResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_id: UUID
    upload_id: UUID
    provider_id: str
    provider_name: str
    model_id: str
    provider_job_id: str | None = None
    prompt: str
    effective_prompt: str | None = None
    settings: VideoGenerationSettings
    effective_seed: int | None = None
    state: VideoJobState
    message: str
    created_at: datetime
    updated_at: datetime
    state_history: list[VideoJobState] = Field(default_factory=lambda: [VideoJobState.QUEUED])
    metadata: VideoMetadata | None = None
    output_filename: str | None = None
    error_code: str | None = None
    error: str | None = None
