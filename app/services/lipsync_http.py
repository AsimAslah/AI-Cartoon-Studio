"""Local-only upload, preview and provider-ready Malayalam lip-sync API."""

from __future__ import annotations

from ipaddress import ip_address
from typing import Literal

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile, status
from fastapi.responses import FileResponse
from pydantic import ValidationError

from app.config import settings
from app.services.lipsync_contract import (
    MAX_FILE_BYTES,
    InputMode,
    LipSyncJobRequest,
    LipSyncJobResponse,
    LipSyncRequest,
    LipSyncUploadResponse,
    MediaValidationError,
    ProviderUnavailableError,
    UnconfiguredLipSyncProvider,
    provider_catalog,
    validate_media_bytes,
)
from app.services.lipsync_jobs import (
    LipSyncJobManager,
    LipSyncJobNotFoundError,
    LipSyncOutputUnavailableError,
)
from app.services.lipsync_store import (
    CorruptUploadError,
    InvalidUploadIdError,
    LipSyncUploadStore,
    UploadNotFoundError,
)

router = APIRouter(prefix="/api/lipsync", tags=["Malayalam lip-sync studio"])
_provider = UnconfiguredLipSyncProvider()
_upload_store = LipSyncUploadStore(settings.lipsync_data_dir)
_job_manager = LipSyncJobManager(settings.lipsync_jobs_dir)


def _require_local_client(request: Request) -> None:
    """Deny direct non-loopback clients for these local-only upload endpoints.

    Uvicorn should also be bound to 127.0.0.1 (the default). TestClient uses
    the non-network client address 'testclient'; it is accepted for testing.
    Do not expose this service to the Internet without real authentication.
    """
    remote = request.client.host if request.client else ""
    if remote == "testclient":
        return
    try:
        if ip_address(remote).is_loopback:
            return
    except ValueError:
        pass
    raise HTTPException(status_code=403, detail="Lip-sync uploads are available only from the local computer.")


def _request_metadata(mode: str, source_name: str, audio_name: str, character_id: str, language: str) -> LipSyncRequest:
    try:
        return LipSyncRequest(
            mode=mode,
            source_filename=source_name,
            audio_filename=audio_name,
            character_id=character_id,
            language=language,
        )
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=f"Invalid lip-sync request: {exc}") from exc


async def _read_media(kind: Literal["image", "audio", "video"], upload: UploadFile) -> bytes:
    try:
        # Read one byte past the limit so oversize uploads are rejected rather
        # than silently truncated. Starlette's multipart parser may have already
        # spooled larger uploads; do not expose this endpoint to untrusted hosts.
        payload = await upload.read(MAX_FILE_BYTES[kind] + 1)
        validate_media_bytes(kind, upload.filename or "", payload)
        return payload
    except MediaValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    finally:
        await upload.close()


@router.get("/capabilities")
async def get_lipsync_capabilities() -> dict[str, object]:
    """Advertise supported input envelopes, NOT the availability of a model."""
    return {
        "language": "ml",
        "input_modes": [mode.value for mode in InputMode],
        "max_file_bytes": MAX_FILE_BYTES.copy(),
        "provider": _provider.capabilities().model_dump(mode="json"),
        "providers": [provider.model_dump(mode="json") for provider in provider_catalog()],
        "real_generation_enabled": False,
        "limits": [
            "Signatures and file sizes only; codecs, duration and playable media are not yet verified.",
            "No real lip-sync model is installed; no output video is produced.",
            "Upload endpoints are local-only and must not be publicly exposed.",
            "Anthropomorphic animal lip-sync remains experimental until visibly verified.",
        ],
    }


async def _validated_payload(
    request: Request,
    mode: str,
    source: UploadFile,
    audio: UploadFile,
    character_id: str,
    language: str,
) -> tuple[LipSyncRequest, str, bytes, bytes]:
    _require_local_client(request)
    metadata = _request_metadata(mode, source.filename or "", audio.filename or "", character_id, language)
    kind: Literal["image", "video"] = "image" if metadata.mode == InputMode.PORTRAIT else "video"
    src = await _read_media(kind, source)
    sound = await _read_media("audio", audio)
    return metadata, kind, src, sound


async def _validate_upload(
    request: Request,
    mode: str,
    source: UploadFile,
    audio: UploadFile,
    character_id: str,
    language: str,
) -> dict[str, object]:
    metadata, kind, src, sound = await _validated_payload(
        request, mode, source, audio, character_id, language
    )
    return {
        "valid": True,
        "mode": metadata.mode.value,
        "language": metadata.language,
        "character_id": metadata.character_id,
        "source": {"filename": metadata.source_filename, "kind": kind, "bytes": len(src)},
        "audio": {"filename": metadata.audio_filename, "kind": "audio", "bytes": len(sound)},
        "decode_verified": False,
        "lip_sync_performed": False,
        "note": "Only preliminary format and size checks passed. No model was run.",
    }


@router.post("/validate")
async def validate_lipsync_upload(
    request: Request,
    mode: str = Form(...),
    source: UploadFile = File(...),
    audio: UploadFile = File(...),
    character_id: str = Form("sheru_bhai"),
    language: str = Form("ml"),
) -> dict[str, object]:
    """Check source/audio input; do not persist or generate video."""
    return await _validate_upload(request, mode, source, audio, character_id, language)


def _upload_response(record) -> LipSyncUploadResponse:
    upload_id = str(record.upload_id)
    return LipSyncUploadResponse(
        **record.model_dump(),
        source_preview_url=f"/api/lipsync/uploads/{upload_id}/media/source",
        audio_preview_url=f"/api/lipsync/uploads/{upload_id}/media/audio",
    )


def _store_error(exc: Exception) -> HTTPException:
    if isinstance(exc, (InvalidUploadIdError, UploadNotFoundError)):
        code = 422 if isinstance(exc, InvalidUploadIdError) else 404
        return HTTPException(status_code=code, detail=str(exc))
    if isinstance(exc, CorruptUploadError):
        return HTTPException(status_code=409, detail=str(exc))
    return HTTPException(status_code=500, detail="Lip-sync storage failed.")


@router.post("/uploads", response_model=LipSyncUploadResponse, status_code=status.HTTP_201_CREATED)
async def create_lipsync_upload(
    request: Request,
    mode: str = Form(...),
    source: UploadFile = File(...),
    audio: UploadFile = File(...),
    character_id: str = Form("sheru_bhai"),
    language: str = Form("ml"),
) -> LipSyncUploadResponse:
    """Persist validated bytes under a UUID for local previews and later inference."""
    metadata, _kind, src, sound = await _validated_payload(
        request, mode, source, audio, character_id, language
    )
    record = _upload_store.create(metadata, src, sound)
    return _upload_response(record)


@router.get("/uploads/{upload_id}", response_model=LipSyncUploadResponse)
async def get_lipsync_upload(request: Request, upload_id: str) -> LipSyncUploadResponse:
    _require_local_client(request)
    try:
        return _upload_response(_upload_store.get(upload_id))
    except (InvalidUploadIdError, UploadNotFoundError, CorruptUploadError) as exc:
        raise _store_error(exc) from exc


@router.get("/uploads/{upload_id}/media/{kind}")
async def get_lipsync_media(request: Request, upload_id: str, kind: str) -> FileResponse:
    _require_local_client(request)
    try:
        path, content_type = _upload_store.media_path(upload_id, kind)
    except (InvalidUploadIdError, UploadNotFoundError, CorruptUploadError) as exc:
        raise _store_error(exc) from exc
    return FileResponse(
        path,
        media_type=content_type,
        headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"},
    )


@router.post("/jobs", response_model=LipSyncJobResponse, status_code=status.HTTP_202_ACCEPTED)
async def submit_lipsync_job(
    request: Request,
    upload_id: str | None = Form(None),
    provider_id: str = Form("none"),
    mode: str | None = Form(None),
    source: UploadFile | None = File(None),
    audio: UploadFile | None = File(None),
    character_id: str = Form("sheru_bhai"),
    language: str = Form("ml"),
) -> LipSyncJobResponse:
    """Submit only when a real provider runtime is registered and available."""
    _require_local_client(request)
    if upload_id is None:
        if mode is None or source is None or audio is None:
            raise HTTPException(status_code=422, detail="Provide a prepared upload ID or complete source and audio files.")
        await _validate_upload(request, mode, source, audio, character_id, language)
        raise HTTPException(
            status_code=503,
            detail="No real lip-sync provider is configured. No job was created, no video was generated, and no API was charged.",
        )
    try:
        record = _upload_store.get(upload_id)
        source_path, _ = _upload_store.media_path(upload_id, "source")
        audio_path, _ = _upload_store.media_path(upload_id, "audio")
        job_request = LipSyncJobRequest(upload_id=record.upload_id, provider_id=provider_id)
        return _job_manager.submit(job_request, record, source_path, audio_path)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=f"Invalid lip-sync job request: {exc}") from exc
    except (InvalidUploadIdError, UploadNotFoundError, CorruptUploadError) as exc:
        raise _store_error(exc) from exc
    except ProviderUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/jobs/{job_id}", response_model=LipSyncJobResponse)
async def get_lipsync_job(request: Request, job_id: str) -> LipSyncJobResponse:
    _require_local_client(request)
    try:
        return _job_manager.get(job_id)
    except LipSyncJobNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/jobs/{job_id}/output")
async def get_lipsync_output(request: Request, job_id: str) -> FileResponse:
    _require_local_client(request)
    try:
        path = _job_manager.output_path(job_id)
    except LipSyncJobNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except LipSyncOutputUnavailableError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return FileResponse(
        path,
        filename=f"malayalam-lipsync-{job_id}.mp4",
        media_type="video/mp4",
        headers={"X-Content-Type-Options": "nosniff"},
    )
