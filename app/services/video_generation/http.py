from __future__ import annotations

from functools import partial
from ipaddress import ip_address

from fastapi import APIRouter, File, HTTPException, Request, UploadFile, status
from fastapi.responses import FileResponse

from app.config import settings
from app.services.video_generation.contracts import (
    VideoGenerationRequest,
    VideoImageResponse,
    VideoJobResponse,
)
from app.services.video_generation.huggingface_provider import VideoProviderError
from app.services.video_generation.jobs import (
    VideoGenerationJobManager,
    VideoJobNotFoundError,
    VideoJobOutputUnavailableError,
)
from app.services.video_generation.media_validation import (
    MAX_IMAGE_BYTES,
    VideoMediaValidationError,
    probe_mp4,
    validate_image_bytes,
)
from app.services.video_generation.providers import build_huggingface_provider
from app.services.video_generation.store import (
    CorruptVideoUploadError,
    InvalidVideoUploadIdError,
    VideoInputStore,
    VideoUploadNotFoundError,
)

router = APIRouter(prefix="/api/video", tags=["AI video studio"])
_store = VideoInputStore(settings.video_generation_data_dir)
_provider, _ffprobe = build_huggingface_provider()
_probe = partial(probe_mp4, ffprobe=_ffprobe) if _ffprobe else None
_jobs = VideoGenerationJobManager(
    settings.video_generation_jobs_dir,
    {_provider.provider_id: _provider},
    _probe,
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
    raise HTTPException(status_code=403, detail="AI Video Studio is available only from the local computer.")


def _store_error(exc: Exception) -> HTTPException:
    if isinstance(exc, InvalidVideoUploadIdError):
        return HTTPException(status_code=422, detail=str(exc))
    if isinstance(exc, VideoUploadNotFoundError):
        return HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, CorruptVideoUploadError):
        return HTTPException(status_code=409, detail=str(exc))
    return HTTPException(status_code=500, detail="AI video input storage failed.")


def _image_response(record) -> VideoImageResponse:
    return VideoImageResponse(
        **record.model_dump(),
        preview_url=f"/api/video/uploads/{record.upload_id}/image",
    )


@router.get("/capabilities")
async def video_capabilities() -> dict[str, object]:
    capabilities = _provider.capabilities()
    return {
        "provider": capabilities.model_dump(mode="json"),
        "max_image_bytes": MAX_IMAGE_BYTES,
        "remote_disclosure": (
            "Generation uploads the selected image and prompt to the configured Hugging Face Space. "
            "It may consume ZeroGPU quota or prepaid credits. Submission occurs only after explicit consent."
        ),
        "character_consistency_guidance": [
            "Describe the character's face, fur, clothing, proportions, and accessories consistently.",
            "Request a continuous shot and explicitly exclude unwanted characters or scene transitions.",
            "Reference conditioning improves consistency but does not guarantee identity preservation.",
        ],
    }


@router.post("/uploads", response_model=VideoImageResponse, status_code=status.HTTP_201_CREATED)
async def create_video_upload(request: Request, image: UploadFile = File(...)) -> VideoImageResponse:
    _require_local(request)
    try:
        content = await image.read(MAX_IMAGE_BYTES + 1)
        validate_image_bytes(image.filename or "", content)
        record = _store.create(image.filename or "", content)
        return _image_response(record)
    except VideoMediaValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    finally:
        await image.close()


@router.get("/uploads/{upload_id}", response_model=VideoImageResponse)
async def get_video_upload(request: Request, upload_id: str) -> VideoImageResponse:
    _require_local(request)
    try:
        return _image_response(_store.get(upload_id))
    except (InvalidVideoUploadIdError, VideoUploadNotFoundError, CorruptVideoUploadError) as exc:
        raise _store_error(exc) from exc


@router.get("/uploads/{upload_id}/image")
async def get_video_image(request: Request, upload_id: str) -> FileResponse:
    _require_local(request)
    try:
        path, content_type = _store.image_path(upload_id)
    except (InvalidVideoUploadIdError, VideoUploadNotFoundError, CorruptVideoUploadError) as exc:
        raise _store_error(exc) from exc
    return FileResponse(
        path,
        media_type=content_type,
        headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"},
    )


@router.post("/jobs", response_model=VideoJobResponse, status_code=status.HTTP_202_ACCEPTED)
async def create_video_job(request: Request, generation: VideoGenerationRequest) -> VideoJobResponse:
    _require_local(request)
    try:
        _store.get(generation.upload_id)
        image_path, _ = _store.image_path(generation.upload_id)
        return _jobs.submit(generation, image_path)
    except (InvalidVideoUploadIdError, VideoUploadNotFoundError, CorruptVideoUploadError) as exc:
        raise _store_error(exc) from exc
    except VideoProviderError as exc:
        raise HTTPException(status_code=503, detail={"code": exc.error_code, "message": str(exc)}) from exc


@router.get("/jobs/{job_id}", response_model=VideoJobResponse)
async def get_video_job(request: Request, job_id: str) -> VideoJobResponse:
    _require_local(request)
    try:
        return _jobs.get(job_id)
    except VideoJobNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/jobs/{job_id}/output")
async def get_video_output(request: Request, job_id: str) -> FileResponse:
    _require_local(request)
    try:
        job = _jobs.get(job_id)
        path = _jobs.output_path(job_id)
    except VideoJobNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except VideoJobOutputUnavailableError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return FileResponse(
        path,
        filename=f"ai-video-{job_id}.mp4",
        media_type="video/mp4",
        headers={
            "X-Content-Type-Options": "nosniff",
            "X-AI-Provider": job.provider_name,
            "X-AI-Model": job.model_id,
        },
    )
