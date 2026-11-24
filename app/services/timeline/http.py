from __future__ import annotations

import os
import tempfile
from ipaddress import ip_address
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile, status
from fastapi.responses import FileResponse

from app.config import settings
from app.services.timeline.contracts import (
    GeneratedClipImportRequest,
    TimelineExportRequest,
    TimelineExportResponse,
    TimelineMediaKind,
    TimelineMediaResponse,
    TimelineProjectDraft,
    TimelineProjectList,
    TimelineProjectRecord,
)
from app.services.timeline.export import (
    PROFILE_DIMENSIONS,
    TimelineExportError,
    TimelineExportManager,
    TimelineExportNotFound,
    TimelineExportUnavailable,
)
from app.services.timeline.media import (
    MAX_MEDIA_BYTES,
    CorruptTimelineMedia,
    InvalidTimelineMediaId,
    TimelineMediaError,
    TimelineMediaNotFound,
    TimelineMediaStore,
    discover_binary,
)
from app.services.timeline.projects import (
    CorruptTimelineProject,
    InvalidTimelineProjectId,
    TimelineProjectError,
    TimelineProjectNotFound,
    TimelineProjectStore,
)


router = APIRouter(prefix="/api/timeline", tags=["Video Timeline Studio"])
_ffmpeg = discover_binary("ffmpeg", os.environ.get("AI_CARTOON_FFMPEG_PATH") or None)
_ffprobe = discover_binary("ffprobe", os.environ.get("AI_CARTOON_FFPROBE_PATH") or None)
_media = TimelineMediaStore(
    settings.timeline_media_dir,
    ffprobe=_ffprobe,
    ffmpeg=_ffmpeg,
)
_projects = TimelineProjectStore(settings.timeline_projects_dir)
_exports = TimelineExportManager(
    settings.timeline_exports_dir,
    _projects,
    _media,
    ffmpeg=_ffmpeg,
    ffprobe=_ffprobe,
)


def _require_local(request: Request) -> None:
    remote = request.client.host if request.client else ""
    if remote == "testclient":
        return
    try:
        if ip_address(remote).is_loopback:
            return
    except ValueError:
        pass
    raise HTTPException(status_code=403, detail="Video Timeline Studio is available only from the local computer.")


def _media_response(record) -> TimelineMediaResponse:
    media_id = str(record.media_id)
    return TimelineMediaResponse(
        **record.model_dump(),
        preview_url=f"/api/timeline/media/{media_id}/file",
        thumbnail_url=f"/api/timeline/media/{media_id}/thumbnail" if record.thumbnail_filename else None,
    )


def _media_http_error(exc: Exception) -> HTTPException:
    if isinstance(exc, InvalidTimelineMediaId):
        return HTTPException(status_code=422, detail=str(exc))
    if isinstance(exc, TimelineMediaNotFound):
        return HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, CorruptTimelineMedia):
        return HTTPException(status_code=409, detail=str(exc))
    if isinstance(exc, TimelineMediaError):
        return HTTPException(status_code=422, detail=str(exc))
    return HTTPException(status_code=500, detail="Timeline media operation failed.")


def _project_http_error(exc: Exception) -> HTTPException:
    if isinstance(exc, InvalidTimelineProjectId):
        return HTTPException(status_code=422, detail=str(exc))
    if isinstance(exc, TimelineProjectNotFound):
        return HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, CorruptTimelineProject):
        return HTTPException(status_code=409, detail=str(exc))
    return HTTPException(status_code=500, detail="Timeline project operation failed.")


def _generated_job_ids() -> list[str]:
    root = settings.video_generation_jobs_dir.resolve()
    if not root.exists():
        return []
    job_ids: list[str] = []
    for directory in root.iterdir():
        if not directory.is_dir():
            continue
        try:
            from uuid import UUID

            parsed = UUID(directory.name)
        except ValueError:
            continue
        if str(parsed) != directory.name.lower():
            continue
        candidate = (directory / "generated.mp4").resolve()
        if candidate.parent == directory.resolve() and candidate.is_file():
            job_ids.append(directory.name)
    return sorted(job_ids)


def _validate_draft_media(draft: TimelineProjectDraft) -> None:
    for clip in draft.clips:
        _path, record = _media.media_path(clip.media_id)
        if record.kind != TimelineMediaKind.CLIP:
            raise TimelineMediaError("Timeline clips must reference uploaded or imported MP4 media.")
        end = clip.trim_end_seconds if clip.trim_end_seconds is not None else record.duration_seconds
        if clip.trim_start_seconds >= record.duration_seconds or end > record.duration_seconds + 0.001:
            raise TimelineMediaError("A clip trim range exceeds its source duration.")
    for track, expected in (
        (draft.voice_track, TimelineMediaKind.VOICE),
        (draft.music_track, TimelineMediaKind.MUSIC),
    ):
        if track:
            _path, record = _media.media_path(track.media_id)
            if record.kind != expected:
                raise TimelineMediaError(f"The {expected.value} track references the wrong media kind.")


async def _save_temporary_upload(upload: UploadFile, limit: int) -> Path:
    settings.timeline_media_dir.mkdir(parents=True, exist_ok=True)
    handle = tempfile.NamedTemporaryFile(dir=settings.timeline_media_dir, suffix=".upload", delete=False)
    path = Path(handle.name)
    written = 0
    try:
        with handle:
            while True:
                chunk = await upload.read(1024 * 1024)
                if not chunk:
                    break
                written += len(chunk)
                if written > limit:
                    raise TimelineMediaError("Timeline media exceeds its configured size limit.")
                handle.write(chunk)
            handle.flush()
            os.fsync(handle.fileno())
        if written == 0:
            raise TimelineMediaError("Timeline media is empty.")
        return path
    except Exception:
        if path.exists():
            path.unlink()
        raise
    finally:
        await upload.close()


@router.get("/capabilities")
async def timeline_capabilities(request: Request) -> dict[str, object]:
    _require_local(request)
    return {
        "ffmpeg_available": _ffmpeg is not None,
        "ffprobe_available": _ffprobe is not None,
        "schema_version": "1.0",
        "export_profiles": {
            profile.value: {"width": dimensions[0], "height": dimensions[1], "frame_rate": 30}
            for profile, dimensions in PROFILE_DIMENSIONS.items()
        },
        "generated_job_ids": _generated_job_ids(),
        "max_media_bytes": {kind.value: limit for kind, limit in MAX_MEDIA_BYTES.items()},
        "limitations": [
            "One local export runs at a time.",
            "Pre-export sequence preview does not include voice or music mixing.",
            "Projects store references to preserved local media; deleting runtime data makes them incomplete.",
        ],
    }


@router.post("/media", response_model=TimelineMediaResponse, status_code=status.HTTP_201_CREATED)
async def upload_timeline_media(
    request: Request,
    kind: TimelineMediaKind = Form(...),
    media: UploadFile = File(...),
) -> TimelineMediaResponse:
    _require_local(request)
    temporary: Path | None = None
    original_filename = media.filename or ""
    try:
        temporary = await _save_temporary_upload(media, MAX_MEDIA_BYTES[kind])
        record = _media.create_from_path(original_filename, temporary, kind)
        return _media_response(record)
    except TimelineMediaError as exc:
        raise _media_http_error(exc) from exc
    finally:
        if temporary and temporary.exists():
            temporary.unlink()


@router.post("/import-generated", response_model=TimelineMediaResponse, status_code=status.HTTP_201_CREATED)
async def import_generated_clip(request: Request, body: GeneratedClipImportRequest) -> TimelineMediaResponse:
    _require_local(request)
    root = settings.video_generation_jobs_dir.resolve()
    directory = (root / str(body.job_id)).resolve()
    source = (directory / "generated.mp4").resolve()
    if directory.parent != root or source.parent != directory or not source.is_file():
        raise HTTPException(status_code=404, detail="Generated AI video clip was not found.")
    try:
        return _media_response(
            _media.create_from_path(f"generated-{body.job_id}.mp4", source, TimelineMediaKind.CLIP)
        )
    except TimelineMediaError as exc:
        raise _media_http_error(exc) from exc


@router.get("/media/{media_id}", response_model=TimelineMediaResponse)
async def get_timeline_media(request: Request, media_id: str) -> TimelineMediaResponse:
    _require_local(request)
    try:
        return _media_response(_media.get(media_id))
    except (InvalidTimelineMediaId, TimelineMediaNotFound, CorruptTimelineMedia) as exc:
        raise _media_http_error(exc) from exc


@router.get("/media/{media_id}/file")
async def preview_timeline_media(request: Request, media_id: str) -> FileResponse:
    _require_local(request)
    try:
        path, record = _media.media_path(media_id)
    except (InvalidTimelineMediaId, TimelineMediaNotFound, CorruptTimelineMedia) as exc:
        raise _media_http_error(exc) from exc
    return FileResponse(
        path,
        media_type=record.content_type,
        headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"},
    )


@router.get("/media/{media_id}/thumbnail")
async def timeline_thumbnail(request: Request, media_id: str) -> FileResponse:
    _require_local(request)
    try:
        path = _media.thumbnail_path(media_id)
    except (InvalidTimelineMediaId, TimelineMediaNotFound, CorruptTimelineMedia) as exc:
        raise _media_http_error(exc) from exc
    return FileResponse(path, media_type="image/jpeg", headers={"Cache-Control": "no-store"})


@router.post("/projects", response_model=TimelineProjectRecord, status_code=status.HTTP_201_CREATED)
async def create_timeline_project(request: Request, draft: TimelineProjectDraft) -> TimelineProjectRecord:
    _require_local(request)
    try:
        _validate_draft_media(draft)
        return _projects.create(draft)
    except TimelineMediaError as exc:
        raise _media_http_error(exc) from exc


@router.get("/projects", response_model=TimelineProjectList)
async def list_timeline_projects(request: Request) -> TimelineProjectList:
    _require_local(request)
    return _projects.list()


@router.get("/projects/{project_id}", response_model=TimelineProjectRecord)
async def get_timeline_project(request: Request, project_id: str) -> TimelineProjectRecord:
    _require_local(request)
    try:
        project = _projects.get(project_id)
        _validate_draft_media(project)
        return project
    except (InvalidTimelineProjectId, TimelineProjectNotFound, CorruptTimelineProject) as exc:
        raise _project_http_error(exc) from exc
    except TimelineMediaError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.put("/projects/{project_id}", response_model=TimelineProjectRecord)
async def update_timeline_project(
    request: Request,
    project_id: str,
    draft: TimelineProjectDraft,
) -> TimelineProjectRecord:
    _require_local(request)
    try:
        _validate_draft_media(draft)
        return _projects.update(project_id, draft)
    except (InvalidTimelineProjectId, TimelineProjectNotFound, CorruptTimelineProject) as exc:
        raise _project_http_error(exc) from exc
    except TimelineMediaError as exc:
        raise _media_http_error(exc) from exc


@router.post("/exports", response_model=TimelineExportResponse, status_code=status.HTTP_202_ACCEPTED)
async def create_timeline_export(request: Request, body: TimelineExportRequest) -> TimelineExportResponse:
    _require_local(request)
    try:
        return _exports.submit(body.project_id)
    except TimelineProjectError as exc:
        raise _project_http_error(exc) from exc
    except (TimelineMediaError, TimelineExportError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/exports/{job_id}", response_model=TimelineExportResponse)
async def get_timeline_export(request: Request, job_id: str) -> TimelineExportResponse:
    _require_local(request)
    try:
        return _exports.get(job_id)
    except TimelineExportNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/exports/{job_id}/output")
async def get_timeline_output(request: Request, job_id: str) -> FileResponse:
    _require_local(request)
    try:
        path = _exports.output_path(job_id)
    except TimelineExportNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except TimelineExportUnavailable as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return FileResponse(
        path,
        filename=f"woodora-timeline-{job_id}.mp4",
        media_type="video/mp4",
        headers={"X-Content-Type-Options": "nosniff"},
    )
