from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator


class TimelineMediaKind(str, Enum):
    CLIP = "clip"
    VOICE = "voice"
    MUSIC = "music"


class TimelineExportProfile(str, Enum):
    HD_720P = "720p"
    FULL_HD_1080P = "1080p"


class TimelineExportState(str, Enum):
    QUEUED = "QUEUED"
    VALIDATING = "VALIDATING"
    NORMALIZING = "NORMALIZING"
    CONCATENATING = "CONCATENATING"
    MIXING_AUDIO = "MIXING_AUDIO"
    VERIFYING = "VERIFYING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class TimelineMediaRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0"] = "1.0"
    media_id: UUID
    kind: TimelineMediaKind
    created_at: datetime
    original_filename: str
    stored_filename: str
    content_type: str
    bytes: int = Field(gt=0)
    duration_seconds: float = Field(gt=0)
    width: int | None = Field(default=None, gt=0)
    height: int | None = Field(default=None, gt=0)
    frame_rate: float | None = Field(default=None, gt=0)
    codec: str
    has_audio: bool
    thumbnail_filename: str | None = None


class TimelineMediaResponse(TimelineMediaRecord):
    preview_url: str
    thumbnail_url: str | None = None


class TimelineClip(BaseModel):
    model_config = ConfigDict(extra="forbid")

    clip_id: UUID = Field(default_factory=uuid4)
    media_id: UUID
    order: int = Field(ge=0)
    trim_start_seconds: float = Field(default=0.0, ge=0)
    trim_end_seconds: float | None = Field(default=None, gt=0)
    volume: float = Field(default=1.0, ge=0, le=2)

    @model_validator(mode="after")
    def valid_trim_range(self) -> "TimelineClip":
        if self.trim_end_seconds is not None and self.trim_end_seconds <= self.trim_start_seconds:
            raise ValueError("Clip trim end must be after trim start.")
        return self


class TimelineAudioTrack(BaseModel):
    model_config = ConfigDict(extra="forbid")

    media_id: UUID
    volume: float = Field(default=1.0, ge=0, le=2)
    start_seconds: float = Field(default=0.0, ge=0)


class TimelineProjectDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0"] = "1.0"
    name: str = Field(min_length=1, max_length=120)
    clips: list[TimelineClip] = Field(default_factory=list, max_length=100)
    voice_track: TimelineAudioTrack | None = None
    music_track: TimelineAudioTrack | None = None
    export_profile: TimelineExportProfile = TimelineExportProfile.HD_720P

    @model_validator(mode="after")
    def valid_clip_order(self) -> "TimelineProjectDraft":
        ids = [clip.clip_id for clip in self.clips]
        if len(ids) != len(set(ids)):
            raise ValueError("Timeline clip IDs must be unique.")
        if sorted(clip.order for clip in self.clips) != list(range(len(self.clips))):
            raise ValueError("Timeline clip order must be contiguous and start at zero.")
        return self


class TimelineProjectRecord(TimelineProjectDraft):
    project_id: UUID
    created_at: datetime
    updated_at: datetime


class TimelineProjectSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_id: UUID
    name: str
    clip_count: int = Field(ge=0)
    export_profile: TimelineExportProfile
    updated_at: datetime


class TimelineProjectList(BaseModel):
    projects: list[TimelineProjectSummary]
    warnings: list[str] = Field(default_factory=list)


class GeneratedClipImportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_id: UUID


class TimelineExportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_id: UUID


class TimelineExportMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    width: int = Field(gt=0)
    height: int = Field(gt=0)
    duration_seconds: float = Field(gt=0)
    frame_rate: float = Field(gt=0)
    codec: str


class TimelineExportResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_id: UUID
    project_id: UUID
    state: TimelineExportState
    message: str
    created_at: datetime
    updated_at: datetime
    state_history: list[TimelineExportState] = Field(default_factory=lambda: [TimelineExportState.QUEUED])
    metadata: TimelineExportMetadata | None = None
    output_filename: str | None = None
    error: str | None = None
