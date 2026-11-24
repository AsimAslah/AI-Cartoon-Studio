"""Provider-independent contract for future *real* audio-driven lip synchronization.

This foundation validates files and requests but deliberately does NOT create a
video or pretend lip-sync is available without a compatible inference backend.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from pathlib import PurePosixPath
from typing import Literal, Protocol
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class MediaValidationError(ValueError):
    """Unsupported, oversized or malformed uploaded media."""


class ProviderUnavailableError(RuntimeError):
    """No real lip-sync inference provider is configured."""


class InputMode(str, Enum):
    PORTRAIT = "portrait"
    VIDEO = "video"


class ProviderAvailability(str, Enum):
    UNAVAILABLE = "unavailable"
    UNSUPPORTED_HARDWARE = "unsupported_hardware"
    NOT_INSTALLED = "not_installed"
    LICENSE_REVIEW = "license_review"
    AVAILABLE = "available"


class LipSyncJobState(str, Enum):
    QUEUED = "QUEUED"
    PREPARING = "PREPARING"
    SUBMITTING = "SUBMITTING"
    PROCESSING = "PROCESSING"
    VERIFYING = "VERIFYING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


# Limits chosen to protect a CPU-only 16 GiB RAM local machine.
MAX_FILE_BYTES = {
    "image": 10 * 1024 * 1024,
    "audio": 20 * 1024 * 1024,
    "video": 100 * 1024 * 1024,
}

ALLOWED_EXTENSIONS = {
    "image": {".png", ".jpg", ".jpeg"},
    "audio": {".wav", ".mp3"},
    "video": {".mp4"},
}


def _safe_suffix(filename: str) -> str:
    if not filename or not filename.strip():
        raise MediaValidationError("Filename is required.")
    if any(ch in filename for ch in ("/", "\\", "\x00")) or filename in (".", ".."):
        raise MediaValidationError("Only a filename, without path components, is accepted.")
    return PurePosixPath(filename).suffix.lower()


def validate_media_bytes(kind: Literal["image", "audio", "video"], filename: str, content: bytes) -> None:
    """Check size, extension and common signatures; not a media decoder.

    Full codec and duration verification must occur before real inference.
    """
    if kind not in MAX_FILE_BYTES:
        raise MediaValidationError("Unknown media kind.")
    ext = _safe_suffix(filename)
    if ext not in ALLOWED_EXTENSIONS[kind]:
        raise MediaValidationError(f"Unsupported {kind} extension: {ext or '(missing)' }.")
    if not content:
        raise MediaValidationError("Uploaded file is empty.")
    if len(content) > MAX_FILE_BYTES[kind]:
        raise MediaValidationError(f"{kind.capitalize()} file exceeds its size limit.")

    if ext == ".png":
        valid = content.startswith(b"\x89PNG\r\n\x1a\n")
    elif ext in {".jpg", ".jpeg"}:
        valid = content.startswith(b"\xff\xd8\xff")
    elif ext == ".wav":
        valid = len(content) >= 12 and content[:4] == b"RIFF" and content[8:12] == b"WAVE"
    elif ext == ".mp3":
        valid = content.startswith(b"ID3") or (
            len(content) >= 2 and content[0] == 0xFF and (content[1] & 0xE0) == 0xE0
        )
    else:  # .mp4
        valid = len(content) >= 12 and content[4:8] == b"ftyp"
    if not valid:
        raise MediaValidationError("Content signature does not match the stated media format.")


class LipSyncRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: InputMode
    source_filename: str = Field(min_length=1, max_length=255)
    audio_filename: str = Field(min_length=1, max_length=255)
    character_id: str = Field(default="sheru_bhai", min_length=1, max_length=64, pattern=r"^[a-zA-Z0-9_-]+$")
    language: Literal["ml"] = "ml"  # Never replace Malayalam audio with English voice.

    @field_validator("source_filename", "audio_filename")
    @classmethod
    def valid_filename(cls, value: str) -> str:
        _safe_suffix(value)
        return value

    @model_validator(mode="after")
    def validate_mode_extensions(self) -> "LipSyncRequest":
        kind = "image" if self.mode == InputMode.PORTRAIT else "video"
        if _safe_suffix(self.source_filename) not in ALLOWED_EXTENSIONS[kind]:
            raise ValueError(f"{self.mode.value} mode requires a valid {kind} file.")
        if _safe_suffix(self.audio_filename) not in ALLOWED_EXTENSIONS["audio"]:
            raise ValueError("Lip-sync requires a .wav or .mp3 audio file.")
        return self


class ProviderCapabilities(BaseModel):
    provider_id: str = "none"
    name: str
    configured: bool
    modes: list[InputMode]
    performs_real_lipsync: bool
    note: str
    availability: ProviderAvailability = ProviderAvailability.UNAVAILABLE
    requires_external_gpu: bool = False
    requirements: list[str] = Field(default_factory=list)
    cost_note: str = "No automatic charges."
    animal_support: Literal["untested", "experimental", "validated"] = "untested"


class StoredMedia(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["image", "video", "audio"]
    original_filename: str
    stored_filename: str
    content_type: str
    bytes: int = Field(gt=0)


class LipSyncUploadRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0"] = "1.0"
    upload_id: UUID
    created_at: datetime
    request: LipSyncRequest
    source: StoredMedia
    audio: StoredMedia
    decode_verified: bool = False
    status: Literal["VALIDATED"] = "VALIDATED"


class LipSyncUploadResponse(LipSyncUploadRecord):
    source_preview_url: str
    audio_preview_url: str


class LipSyncJobRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    upload_id: UUID
    provider_id: str = Field(min_length=1, max_length=80, pattern=r"^[a-z0-9_-]+$")


class LipSyncJobResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_id: UUID
    upload_id: UUID
    provider_id: str
    state: LipSyncJobState
    message: str
    created_at: datetime
    updated_at: datetime
    state_history: list[LipSyncJobState] = Field(default_factory=lambda: [LipSyncJobState.QUEUED])
    output_filename: str | None = None
    error: str | None = None


class LipSyncProvider(Protocol):
    def capabilities(self) -> ProviderCapabilities: ...

    def submit(self, request: LipSyncRequest, source: bytes, audio: bytes) -> str: ...


class UnconfiguredLipSyncProvider:
    """Safe default: never call an API, charge credits, or fabricate lip movement."""

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            provider_id="none",
            name="none",
            configured=False,
            modes=[],
            performs_real_lipsync=False,
            note="Lip-sync not available: configure and verify an inference backend.",
        )

    def submit(self, request: LipSyncRequest, source: bytes, audio: bytes) -> str:
        raise ProviderUnavailableError(
            "No lip-sync provider configured. No video was generated and no API was charged."
        )


def provider_catalog() -> list[ProviderCapabilities]:
    """Describe researched options without claiming that they are installed."""
    return [
        UnconfiguredLipSyncProvider().capabilities(),
        ProviderCapabilities(
            provider_id="latentsync_local",
            name="LatentSync (local CUDA)",
            configured=False,
            modes=[InputMode.VIDEO],
            performs_real_lipsync=True,
            availability=ProviderAvailability.UNSUPPORTED_HARDWARE,
            requires_external_gpu=True,
            requirements=["NVIDIA CUDA GPU", "8 GB VRAM minimum for LatentSync 1.5", "separate model checkpoints"],
            note="Not installed: this computer has integrated Radeon graphics and no CUDA GPU.",
            animal_support="experimental",
        ),
        ProviderCapabilities(
            provider_id="musetalk_local",
            name="MuseTalk (local CUDA)",
            configured=False,
            modes=[InputMode.VIDEO],
            performs_real_lipsync=True,
            availability=ProviderAvailability.NOT_INSTALLED,
            requires_external_gpu=True,
            requirements=["NVIDIA CUDA GPU with at least 4 GB VRAM", "model weights", "third-party dependency review"],
            note="Not installed; CUDA runtime, third-party dependencies, and animal-face behavior require verification.",
            animal_support="experimental",
        ),
        ProviderCapabilities(
            provider_id="external_gpu",
            name="External GPU endpoint",
            configured=False,
            modes=[InputMode.PORTRAIT, InputMode.VIDEO],
            performs_real_lipsync=True,
            availability=ProviderAvailability.UNAVAILABLE,
            requires_external_gpu=True,
            requirements=["user-approved endpoint", "credential configuration", "cost disclosure", "verified MP4 response"],
            note="No endpoint or credentials are configured. The application makes no paid calls.",
            animal_support="untested",
        ),
    ]
