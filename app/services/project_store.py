from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID, uuid4

from pydantic import ValidationError

from app.models import PROJECT_SCHEMA_VERSION, ProjectCreateRequest, ProjectRecord, ProjectSummary, ProjectUpdateRequest


class ProjectStoreError(Exception):
    pass


class InvalidProjectIdError(ProjectStoreError):
    pass


class ProjectNotFoundError(ProjectStoreError):
    pass


class CorruptProjectError(ProjectStoreError):
    pass


class UnsupportedProjectVersionError(ProjectStoreError):
    pass


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ProjectStore:
    def __init__(self, data_dir: Path):
        self.data_dir = data_dir.resolve()

    @staticmethod
    def normalize_project_id(project_id: str | UUID) -> UUID:
        try:
            parsed = project_id if isinstance(project_id, UUID) else UUID(str(project_id))
        except (ValueError, TypeError, AttributeError) as exc:
            raise InvalidProjectIdError("Project ID must be a valid UUID.") from exc
        if str(parsed) != str(project_id).lower():
            raise InvalidProjectIdError("Project ID must use the canonical UUID format.")
        return parsed

    def _path_for(self, project_id: str | UUID) -> Path:
        parsed = self.normalize_project_id(project_id)
        path = (self.data_dir / f"{parsed}.json").resolve()
        if path.parent != self.data_dir:
            raise InvalidProjectIdError("Project path escapes the project data directory.")
        return path

    def _atomic_write(self, path: Path, record: ProjectRecord) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        payload = record.model_dump_json(indent=2)
        temporary: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", newline="\n", dir=self.data_dir, suffix=".tmp", delete=False
            ) as handle:
                temporary = Path(handle.name)
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, path)
        finally:
            if temporary and temporary.exists():
                temporary.unlink()

    def create(self, request: ProjectCreateRequest) -> ProjectRecord:
        now = utc_now()
        record = ProjectRecord(
            **request.model_dump(), project_id=uuid4(), created_at=now, updated_at=now
        )
        self._atomic_write(self._path_for(record.project_id), record)
        return record

    def get(self, project_id: str | UUID) -> ProjectRecord:
        path = self._path_for(project_id)
        if not path.is_file():
            raise ProjectNotFoundError("Project was not found.")
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise CorruptProjectError("Project file is unreadable or contains invalid JSON.") from exc
        if not isinstance(raw, dict):
            raise CorruptProjectError("Project JSON must be an object.")
        if raw.get("schema_version") != PROJECT_SCHEMA_VERSION:
            raise UnsupportedProjectVersionError(
                f"Unsupported project schema version: {raw.get('schema_version')!r}."
            )
        try:
            record = ProjectRecord.model_validate(raw)
        except ValidationError as exc:
            raise CorruptProjectError("Project file does not match the project schema.") from exc
        if record.project_id != self.normalize_project_id(project_id):
            raise CorruptProjectError("Project ID in file does not match filename.")
        return record

    def update(self, project_id: str | UUID, request: ProjectUpdateRequest) -> ProjectRecord:
        existing = self.get(project_id)
        record = ProjectRecord(
            **request.model_dump(),
            project_id=existing.project_id,
            created_at=existing.created_at,
            updated_at=utc_now(),
        )
        self._atomic_write(self._path_for(existing.project_id), record)
        return record

    def list(self) -> tuple[list[ProjectSummary], list[str]]:
        if not self.data_dir.is_dir():
            return [], []
        projects: list[ProjectSummary] = []
        warnings: list[str] = []
        for path in sorted(self.data_dir.glob("*.json")):
            try:
                record = self.get(path.stem)
            except ProjectStoreError as exc:
                warnings.append(f"Skipped {path.name}: {exc}")
                continue
            projects.append(
                ProjectSummary(
                    project_id=record.project_id,
                    name=record.name,
                    scene_count=len(record.storyboard.scenes),
                    updated_at=record.updated_at,
                )
            )
        projects.sort(key=lambda project: project.updated_at, reverse=True)
        return projects, warnings
