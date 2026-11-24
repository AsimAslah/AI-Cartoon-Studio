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
    IMAGE = "image"
    LOGO = "logo"
    CHARACTER_REFERENCE = "character_reference"


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


class TimelineProjectKind(str, Enum):
    TIMELINE = "timeline"
    ADVERTISEMENT = "advertisement"


class TimelineSceneType(str, Enum):
    VIDEO = "video"
    STILL = "still"
    TITLE_CARD = "title_card"
    BRANDING_CARD = "branding_card"


class TimelineTransition(str, Enum):
    CUT = "cut"
    CROSSFADE = "crossfade"


class TimelineTextPosition(str, Enum):
    TOP = "top"
    CENTER = "center"
    LOWER_THIRD = "lower_third"


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
    duration_seconds: float = Field(ge=0)
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
    media_id: UUID | None = None
    order: int = Field(ge=0)
    trim_start_seconds: float = Field(default=0.0, ge=0)
    trim_end_seconds: float | None = Field(default=None, gt=0)
    volume: float = Field(default=1.0, ge=0, le=2)
    scene_type: TimelineSceneType = TimelineSceneType.VIDEO
    slot_key: str | None = Field(default=None, max_length=80, pattern=r"^[a-z0-9_-]+$")
    slot_title: str | None = Field(default=None, max_length=120)
    slot_description: str | None = Field(default=None, max_length=600)
    duration_seconds: float = Field(default=3.0, ge=0.1, le=60)
    fade_in_seconds: float = Field(default=0.0, ge=0, le=5)
    fade_out_seconds: float = Field(default=0.0, ge=0, le=5)
    transition_to_next: TimelineTransition = TimelineTransition.CUT
    transition_duration_seconds: float = Field(default=0.5, ge=0.1, le=3)
    title_text: str | None = Field(default=None, max_length=200)
    overlay_text: str | None = Field(default=None, max_length=300)
    text_position: TimelineTextPosition = TimelineTextPosition.LOWER_THIRD
    font_size: int = Field(default=48, ge=12, le=96)
    brightness: float = Field(default=0.0, ge=-1, le=1)
    contrast: float = Field(default=1.0, ge=0.5, le=2)
    logo_media_id: UUID | None = None
    requires_verified_lipsync: bool = False
    lipsync_verified: bool = False

    @model_validator(mode="after")
    def valid_trim_range(self) -> "TimelineClip":
        if self.trim_end_seconds is not None and self.trim_end_seconds <= self.trim_start_seconds:
            raise ValueError("Clip trim end must be after trim start.")
        if self.scene_type in {TimelineSceneType.TITLE_CARD, TimelineSceneType.BRANDING_CARD}:
            if not self.title_text or not self.title_text.strip():
                raise ValueError("Title and branding cards require title text.")
        if self.requires_verified_lipsync and self.media_id and not self.lipsync_verified:
            raise ValueError("This scene accepts only explicitly verified lip-sync footage.")
        return self


class TimelineAudioTrack(BaseModel):
    model_config = ConfigDict(extra="forbid")

    media_id: UUID
    volume: float = Field(default=1.0, ge=0, le=2)
    start_seconds: float = Field(default=0.0, ge=0)


class TimelineProjectDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0", "1.1"] = "1.1"
    name: str = Field(min_length=1, max_length=120)
    project_kind: TimelineProjectKind = TimelineProjectKind.TIMELINE
    template_id: str | None = Field(default=None, max_length=80, pattern=r"^[a-z0-9_-]+$")
    clips: list[TimelineClip] = Field(default_factory=list, max_length=100)
    voice_track: TimelineAudioTrack | None = None
    music_track: TimelineAudioTrack | None = None
    character_reference_ids: list[UUID] = Field(default_factory=list, max_length=50)
    export_profile: TimelineExportProfile = TimelineExportProfile.HD_720P

    @model_validator(mode="after")
    def valid_clip_order(self) -> "TimelineProjectDraft":
        ids = [clip.clip_id for clip in self.clips]
        if len(ids) != len(set(ids)):
            raise ValueError("Timeline clip IDs must be unique.")
        if sorted(clip.order for clip in self.clips) != list(range(len(self.clips))):
            raise ValueError("Timeline clip order must be contiguous and start at zero.")
        if len(self.character_reference_ids) != len(set(self.character_reference_ids)):
            raise ValueError("Character reference IDs must be unique.")
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


class CharacterReferenceDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0"] = "1.0"
    name: str = Field(min_length=1, max_length=120)
    visual_description: str = Field(min_length=1, max_length=1200)
    clothing_accessories: str = Field(default="", max_length=800)
    notes: str = Field(default="", max_length=1200)
    image_media_ids: list[UUID] = Field(default_factory=list, max_length=20)

    @model_validator(mode="after")
    def unique_images(self) -> "CharacterReferenceDraft":
        if len(self.image_media_ids) != len(set(self.image_media_ids)):
            raise ValueError("Character reference image IDs must be unique.")
        return self


class CharacterReferenceRecord(CharacterReferenceDraft):
    reference_id: UUID
    created_at: datetime
    updated_at: datetime


class CharacterReferenceSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reference_id: UUID
    name: str
    image_count: int = Field(ge=0)
    updated_at: datetime


class CharacterReferenceList(BaseModel):
    references: list[CharacterReferenceSummary]
    warnings: list[str] = Field(default_factory=list)
