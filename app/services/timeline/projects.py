from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID, uuid4

from pydantic import ValidationError

from app.services.timeline.contracts import (
    TimelineProjectDraft,
    TimelineProjectList,
    TimelineProjectRecord,
    TimelineProjectSummary,
)


class TimelineProjectError(Exception):
    pass


class InvalidTimelineProjectId(TimelineProjectError):
    pass


class TimelineProjectNotFound(TimelineProjectError):
    pass


class CorruptTimelineProject(TimelineProjectError):
    pass


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class TimelineProjectStore:
    def __init__(self, data_dir: Path):
        self.data_dir = data_dir.resolve()

    @staticmethod
    def normalize_id(project_id: str | UUID) -> UUID:
        try:
            parsed = project_id if isinstance(project_id, UUID) else UUID(str(project_id))
        except (ValueError, TypeError, AttributeError) as exc:
            raise InvalidTimelineProjectId("Timeline project ID must be a valid UUID.") from exc
        if str(parsed) != str(project_id).lower():
            raise InvalidTimelineProjectId("Timeline project ID must use canonical UUID format.")
        return parsed

    def _path(self, project_id: str | UUID) -> Path:
        parsed = self.normalize_id(project_id)
        path = (self.data_dir / f"{parsed}.json").resolve()
        if path.parent != self.data_dir:
            raise InvalidTimelineProjectId("Timeline project path escaped its configured directory.")
        return path

    @staticmethod
    def _atomic_write(path: Path, record: TimelineProjectRecord) -> None:
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

    def create(self, draft: TimelineProjectDraft) -> TimelineProjectRecord:
        project_id = uuid4()
        now = utc_now()
        record = TimelineProjectRecord(
            **draft.model_dump(),
            project_id=project_id,
            created_at=now,
            updated_at=now,
        )
        self._atomic_write(self._path(project_id), record)
        return record

    def get(self, project_id: str | UUID) -> TimelineProjectRecord:
        path = self._path(project_id)
        if not path.is_file():
            raise TimelineProjectNotFound("Timeline project was not found.")
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            if payload.get("schema_version") != "1.0":
                raise CorruptTimelineProject("Unsupported timeline project schema version.")
            record = TimelineProjectRecord.model_validate(payload)
        except CorruptTimelineProject:
            raise
        except (OSError, json.JSONDecodeError, ValidationError, AttributeError) as exc:
            raise CorruptTimelineProject("Timeline project metadata is corrupt.") from exc
        if record.project_id != self.normalize_id(project_id):
            raise CorruptTimelineProject("Timeline project ID does not match its filename.")
        return record

    def update(self, project_id: str | UUID, draft: TimelineProjectDraft) -> TimelineProjectRecord:
        existing = self.get(project_id)
        record = TimelineProjectRecord(
            **draft.model_dump(),
            project_id=existing.project_id,
            created_at=existing.created_at,
            updated_at=utc_now(),
        )
        self._atomic_write(self._path(existing.project_id), record)
        return record

    def list(self) -> TimelineProjectList:
        if not self.data_dir.exists():
            return TimelineProjectList(projects=[])
        projects: list[TimelineProjectSummary] = []
        warnings: list[str] = []
        for path in sorted(self.data_dir.glob("*.json")):
            try:
                record = self.get(path.stem)
                projects.append(
                    TimelineProjectSummary(
                        project_id=record.project_id,
                        name=record.name,
                        clip_count=len(record.clips),
                        export_profile=record.export_profile,
                        updated_at=record.updated_at,
                    )
                )
            except TimelineProjectError:
                warnings.append(f"Skipped invalid timeline project {path.name}.")
        projects.sort(key=lambda project: project.updated_at, reverse=True)
        return TimelineProjectList(projects=projects, warnings=warnings)
