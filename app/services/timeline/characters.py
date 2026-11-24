from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID, uuid4

from pydantic import ValidationError

from app.services.timeline.contracts import (
    CharacterReferenceDraft,
    CharacterReferenceList,
    CharacterReferenceRecord,
    CharacterReferenceSummary,
)


class CharacterReferenceError(Exception):
    pass


class InvalidCharacterReferenceId(CharacterReferenceError):
    pass


class CharacterReferenceNotFound(CharacterReferenceError):
    pass


class CorruptCharacterReference(CharacterReferenceError):
    pass


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class CharacterReferenceStore:
    def __init__(self, data_dir: Path):
        self.data_dir = data_dir.resolve()

    @staticmethod
    def normalize_id(reference_id: str | UUID) -> UUID:
        try:
            parsed = reference_id if isinstance(reference_id, UUID) else UUID(str(reference_id))
        except (ValueError, TypeError, AttributeError) as exc:
            raise InvalidCharacterReferenceId("Character reference ID must be a valid UUID.") from exc
        if str(parsed) != str(reference_id).lower():
            raise InvalidCharacterReferenceId("Character reference ID must use canonical UUID format.")
        return parsed

    def _path(self, reference_id: str | UUID) -> Path:
        parsed = self.normalize_id(reference_id)
        path = (self.data_dir / f"{parsed}.json").resolve()
        if path.parent != self.data_dir:
            raise InvalidCharacterReferenceId("Character reference path escaped its configured directory.")
        return path

    @staticmethod
    def _atomic_write(path: Path, record: CharacterReferenceRecord) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(dir=path.parent, suffix=".tmp", delete=False) as handle:
                temporary = Path(handle.name)
                handle.write(record.model_dump_json(indent=2).encode("utf-8"))
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, path)
        finally:
            if temporary and temporary.exists():
                temporary.unlink()

    def create(self, draft: CharacterReferenceDraft) -> CharacterReferenceRecord:
        now = utc_now()
        record = CharacterReferenceRecord(
            **draft.model_dump(),
            reference_id=uuid4(),
            created_at=now,
            updated_at=now,
        )
        self._atomic_write(self._path(record.reference_id), record)
        return record

    def get(self, reference_id: str | UUID) -> CharacterReferenceRecord:
        path = self._path(reference_id)
        if not path.is_file():
            raise CharacterReferenceNotFound("Character reference was not found.")
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            if payload.get("schema_version") != "1.0":
                raise CorruptCharacterReference("Unsupported character reference schema version.")
            record = CharacterReferenceRecord.model_validate(payload)
        except CorruptCharacterReference:
            raise
        except (OSError, json.JSONDecodeError, ValidationError, AttributeError) as exc:
            raise CorruptCharacterReference("Character reference metadata is corrupt.") from exc
        if record.reference_id != self.normalize_id(reference_id):
            raise CorruptCharacterReference("Character reference ID does not match its filename.")
        return record

    def update(self, reference_id: str | UUID, draft: CharacterReferenceDraft) -> CharacterReferenceRecord:
        existing = self.get(reference_id)
        record = CharacterReferenceRecord(
            **draft.model_dump(),
            reference_id=existing.reference_id,
            created_at=existing.created_at,
            updated_at=utc_now(),
        )
        self._atomic_write(self._path(existing.reference_id), record)
        return record

    def list(self) -> CharacterReferenceList:
        if not self.data_dir.exists():
            return CharacterReferenceList(references=[])
        references: list[CharacterReferenceSummary] = []
        warnings: list[str] = []
        for path in sorted(self.data_dir.glob("*.json")):
            try:
                record = self.get(path.stem)
                references.append(CharacterReferenceSummary(
                    reference_id=record.reference_id,
                    name=record.name,
                    image_count=len(record.image_media_ids),
                    updated_at=record.updated_at,
                ))
            except CharacterReferenceError:
                warnings.append(f"Skipped invalid character reference {path.name}.")
        references.sort(key=lambda item: item.updated_at, reverse=True)
        return CharacterReferenceList(references=references, warnings=warnings)
