"""Safe local persistence for validated Malayalam lip-sync source media."""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID, uuid4

from pydantic import ValidationError

from app.services.lipsync_contract import LipSyncRequest, LipSyncUploadRecord, StoredMedia


class LipSyncStoreError(Exception):
    pass


class InvalidUploadIdError(LipSyncStoreError):
    pass


class UploadNotFoundError(LipSyncStoreError):
    pass


class CorruptUploadError(LipSyncStoreError):
    pass


CONTENT_TYPES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".wav": "audio/wav",
    ".mp3": "audio/mpeg",
    ".mp4": "video/mp4",
}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class LipSyncUploadStore:
    def __init__(self, data_dir: Path):
        self.data_dir = data_dir.resolve()

    @staticmethod
    def normalize_upload_id(upload_id: str | UUID) -> UUID:
        try:
            parsed = upload_id if isinstance(upload_id, UUID) else UUID(str(upload_id))
        except (ValueError, TypeError, AttributeError) as exc:
            raise InvalidUploadIdError("Upload ID must be a valid UUID.") from exc
        if str(parsed) != str(upload_id).lower():
            raise InvalidUploadIdError("Upload ID must use canonical UUID format.")
        return parsed

    def _directory(self, upload_id: str | UUID) -> Path:
        parsed = self.normalize_upload_id(upload_id)
        directory = (self.data_dir / str(parsed)).resolve()
        if directory.parent != self.data_dir:
            raise InvalidUploadIdError("Upload path escapes the lip-sync data directory.")
        return directory

    @staticmethod
    def _atomic_bytes(path: Path, payload: bytes) -> None:
        temporary: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(dir=path.parent, suffix=".tmp", delete=False) as handle:
                temporary = Path(handle.name)
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, path)
        finally:
            if temporary and temporary.exists():
                temporary.unlink()

    @staticmethod
    def _atomic_json(path: Path, record: LipSyncUploadRecord) -> None:
        LipSyncUploadStore._atomic_bytes(path, record.model_dump_json(indent=2).encode("utf-8"))

    def create(self, request: LipSyncRequest, source: bytes, audio: bytes) -> LipSyncUploadRecord:
        upload_id = uuid4()
        directory = self._directory(upload_id)
        directory.mkdir(parents=True, exist_ok=False)
        source_suffix = Path(request.source_filename).suffix.lower()
        audio_suffix = Path(request.audio_filename).suffix.lower()
        source_name = f"source{source_suffix}"
        audio_name = f"audio{audio_suffix}"
        self._atomic_bytes(directory / source_name, source)
        self._atomic_bytes(directory / audio_name, audio)
        source_kind = "image" if request.mode.value == "portrait" else "video"
        record = LipSyncUploadRecord(
            upload_id=upload_id,
            created_at=utc_now(),
            request=request,
            source=StoredMedia(
                kind=source_kind,
                original_filename=request.source_filename,
                stored_filename=source_name,
                content_type=CONTENT_TYPES[source_suffix],
                bytes=len(source),
            ),
            audio=StoredMedia(
                kind="audio",
                original_filename=request.audio_filename,
                stored_filename=audio_name,
                content_type=CONTENT_TYPES[audio_suffix],
                bytes=len(audio),
            ),
        )
        self._atomic_json(directory / "metadata.json", record)
        return record

    def get(self, upload_id: str | UUID) -> LipSyncUploadRecord:
        metadata = self._directory(upload_id) / "metadata.json"
        if not metadata.is_file():
            raise UploadNotFoundError("Lip-sync upload was not found.")
        try:
            raw = json.loads(metadata.read_text(encoding="utf-8"))
            if raw.get("schema_version") != "1.0":
                raise CorruptUploadError("Unsupported lip-sync upload schema version.")
            record = LipSyncUploadRecord.model_validate(raw)
        except CorruptUploadError:
            raise
        except (OSError, json.JSONDecodeError, ValidationError) as exc:
            raise CorruptUploadError("Lip-sync upload metadata is corrupt.") from exc
        if record.upload_id != self.normalize_upload_id(upload_id):
            raise CorruptUploadError("Lip-sync upload metadata ID does not match its directory.")
        return record

    def media_path(self, upload_id: str | UUID, kind: str) -> tuple[Path, str]:
        if kind not in {"source", "audio"}:
            raise UploadNotFoundError("Requested lip-sync media was not found.")
        record = self.get(upload_id)
        media = record.source if kind == "source" else record.audio
        directory = self._directory(record.upload_id)
        path = (directory / media.stored_filename).resolve()
        if path.parent != directory or not path.is_file() or path.stat().st_size != media.bytes:
            raise CorruptUploadError("Stored lip-sync media is missing or has changed.")
        return path, media.content_type
