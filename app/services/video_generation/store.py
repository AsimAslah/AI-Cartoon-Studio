from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID, uuid4

from pydantic import ValidationError

from app.services.video_generation.contracts import VideoImageRecord
from app.services.video_generation.media_validation import IMAGE_CONTENT_TYPES, validate_image_bytes


class VideoInputStoreError(Exception):
    pass


class InvalidVideoUploadIdError(VideoInputStoreError):
    pass


class VideoUploadNotFoundError(VideoInputStoreError):
    pass


class CorruptVideoUploadError(VideoInputStoreError):
    pass


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class VideoInputStore:
    def __init__(self, data_dir: Path):
        self.data_dir = data_dir.resolve()

    @staticmethod
    def normalize_upload_id(upload_id: str | UUID) -> UUID:
        try:
            parsed = upload_id if isinstance(upload_id, UUID) else UUID(str(upload_id))
        except (ValueError, TypeError, AttributeError) as exc:
            raise InvalidVideoUploadIdError("Video upload ID must be a valid UUID.") from exc
        if str(parsed) != str(upload_id).lower():
            raise InvalidVideoUploadIdError("Video upload ID must use canonical UUID format.")
        return parsed

    def _directory(self, upload_id: str | UUID) -> Path:
        parsed = self.normalize_upload_id(upload_id)
        directory = (self.data_dir / str(parsed)).resolve()
        if directory.parent != self.data_dir:
            raise InvalidVideoUploadIdError("Video upload path escapes its configured directory.")
        return directory

    @staticmethod
    def _atomic_write(path: Path, content: bytes) -> None:
        temporary: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(dir=path.parent, suffix=".tmp", delete=False) as handle:
                temporary = Path(handle.name)
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, path)
        finally:
            if temporary and temporary.exists():
                temporary.unlink()

    def create(self, filename: str, content: bytes) -> VideoImageRecord:
        suffix = validate_image_bytes(filename, content)
        upload_id = uuid4()
        directory = self._directory(upload_id)
        directory.mkdir(parents=True, exist_ok=False)
        stored_filename = f"reference{suffix}"
        self._atomic_write(directory / stored_filename, content)
        record = VideoImageRecord(
            upload_id=upload_id,
            created_at=utc_now(),
            original_filename=filename,
            stored_filename=stored_filename,
            content_type=IMAGE_CONTENT_TYPES[suffix],
            bytes=len(content),
        )
        self._atomic_write(directory / "metadata.json", record.model_dump_json(indent=2).encode("utf-8"))
        return record

    def get(self, upload_id: str | UUID) -> VideoImageRecord:
        path = self._directory(upload_id) / "metadata.json"
        if not path.is_file():
            raise VideoUploadNotFoundError("Video reference upload was not found.")
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            if payload.get("schema_version") != "1.0":
                raise CorruptVideoUploadError("Unsupported video upload schema version.")
            record = VideoImageRecord.model_validate(payload)
        except CorruptVideoUploadError:
            raise
        except (OSError, json.JSONDecodeError, ValidationError) as exc:
            raise CorruptVideoUploadError("Video upload metadata is corrupt.") from exc
        if record.upload_id != self.normalize_upload_id(upload_id):
            raise CorruptVideoUploadError("Video upload metadata ID does not match its directory.")
        return record

    def image_path(self, upload_id: str | UUID) -> tuple[Path, str]:
        record = self.get(upload_id)
        directory = self._directory(record.upload_id)
        path = (directory / record.stored_filename).resolve()
        if path.parent != directory or not path.is_file() or path.stat().st_size != record.bytes:
            raise CorruptVideoUploadError("Stored reference image is missing or has changed.")
        return path, record.content_type
