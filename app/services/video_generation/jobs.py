from __future__ import annotations

import threading
from concurrent.futures import Future, ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Protocol
from uuid import UUID, uuid4

from app.services.render_verifier import verify_mp4
from app.services.video_generation.contracts import (
    VideoGenerationRequest,
    VideoJobResponse,
    VideoJobState,
    VideoMetadata,
    VideoProviderCapabilities,
    VideoProviderResult,
)
from app.services.video_generation.huggingface_provider import VideoProviderError, VideoProviderNotConfiguredError


class VideoJobError(Exception):
    pass


class VideoJobNotFoundError(VideoJobError):
    pass


class VideoJobOutputUnavailableError(VideoJobError):
    pass


class VideoGenerationProvider(Protocol):
    def capabilities(self) -> VideoProviderCapabilities: ...

    def generate(
        self,
        request: VideoGenerationRequest,
        image_path: Path,
        output_dir: Path,
        state_callback: Callable[[str, str | None], None],
    ) -> VideoProviderResult: ...


VideoProbe = Callable[[Path], VideoMetadata]


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class VideoGenerationJobManager:
    def __init__(self, output_dir: Path, providers: dict[str, VideoGenerationProvider], probe: VideoProbe | None):
        self.output_dir = output_dir.resolve()
        self.providers = providers
        self.probe = probe
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="ai-video-generation")
        self._jobs: dict[UUID, VideoJobResponse] = {}
        self._futures: dict[UUID, Future[None]] = {}
        self._lock = threading.RLock()

    def submit(self, request: VideoGenerationRequest, image_path: Path) -> VideoJobResponse:
        provider = self.providers.get(request.provider_id)
        if provider is None:
            raise VideoProviderNotConfiguredError("Selected video provider is not registered.")
        capabilities = provider.capabilities()
        if not capabilities.configured:
            raise VideoProviderNotConfiguredError(capabilities.note)
        if self.probe is None:
            raise VideoProviderNotConfiguredError("ffprobe is required before remote video generation can be enabled.")
        job_id = uuid4()
        now = utc_now()
        job = VideoJobResponse(
            job_id=job_id,
            upload_id=request.upload_id,
            provider_id=capabilities.provider_id,
            provider_name=capabilities.name,
            model_id=capabilities.model_id,
            prompt=request.prompt,
            settings=request.settings,
            state=VideoJobState.QUEUED,
            message="AI video job queued behind any active generation.",
            created_at=now,
            updated_at=now,
        )
        with self._lock:
            self._jobs[job_id] = job
            self._futures[job_id] = self._executor.submit(self._execute, job_id, provider, request, image_path)
        return job.model_copy(deep=True)

    def _set_state(
        self,
        job_id: UUID,
        state: VideoJobState,
        message: str,
        *,
        provider_job_id: str | None = None,
        metadata: VideoMetadata | None = None,
        output_filename: str | None = None,
        effective_prompt: str | None = None,
        effective_seed: int | None = None,
        error_code: str | None = None,
        diagnostic_code: str | None = None,
        error: str | None = None,
    ) -> None:
        with self._lock:
            current = self._jobs[job_id]
            update = {
                "state": state,
                "message": message,
                "updated_at": utc_now(),
                "state_history": [*current.state_history, state] if current.state != state else current.state_history,
                "provider_job_id": provider_job_id or current.provider_job_id,
                "metadata": metadata or current.metadata,
                "output_filename": output_filename or current.output_filename,
                "effective_prompt": effective_prompt or current.effective_prompt,
                "effective_seed": effective_seed if effective_seed is not None else current.effective_seed,
                "error_code": error_code,
                "diagnostic_code": diagnostic_code,
                "error": error,
            }
            self._jobs[job_id] = current.model_copy(update=update)

    def _provider_state(self, job_id: UUID, state: str, provider_job_id: str | None) -> None:
        mapped = VideoJobState(state)
        messages = {
            VideoJobState.SUBMITTED: "Request submitted to the Hugging Face Space.",
            VideoJobState.PROVIDER_QUEUED: "Hugging Face accepted the request and placed it in its queue.",
            VideoJobState.RUNNING: "The remote GPU is performing LTX image-to-video inference.",
            VideoJobState.DOWNLOADING: "Inference finished; downloading the provider output.",
        }
        self._set_state(job_id, mapped, messages[mapped], provider_job_id=provider_job_id)

    def _execute(
        self,
        job_id: UUID,
        provider: VideoGenerationProvider,
        request: VideoGenerationRequest,
        image_path: Path,
    ) -> None:
        directory = (self.output_dir / str(job_id)).resolve()
        try:
            if directory.parent != self.output_dir:
                raise VideoJobError("Video output path escaped its configured directory.")
            self._set_state(job_id, VideoJobState.VALIDATING, "Revalidating the stored image and provider settings.")
            if not image_path.is_file():
                raise VideoJobError("Stored reference image is missing.")
            directory.mkdir(parents=True, exist_ok=False)
            self._set_state(
                job_id,
                VideoJobState.UPLOADING,
                "Uploading the user-approved reference image and prompt to Hugging Face.",
            )
            result = provider.generate(
                request,
                image_path,
                directory,
                lambda state, provider_id: self._provider_state(job_id, state, provider_id),
            )
            self._set_state(
                job_id,
                VideoJobState.VERIFYING,
                "Inspecting the downloaded MP4 with ffprobe.",
                provider_job_id=result.provider_job_id,
                effective_prompt=result.effective_prompt,
                effective_seed=result.effective_seed,
            )
            output = Path(result.output_path).resolve()
            if output.parent != directory or not verify_mp4(output):
                raise VideoJobError("Provider output was missing, unsafe, or failed MP4 envelope validation.")
            if self.probe is None:
                raise VideoJobError("ffprobe metadata verification is unavailable.")
            metadata = self.probe(output)
            self._set_state(
                job_id,
                VideoJobState.COMPLETED,
                "Real provider output passed MP4 and metadata verification.",
                metadata=metadata,
                output_filename=output.name,
            )
        except Exception as exc:
            code = exc.error_code if isinstance(exc, VideoProviderError) else "generation_failed"
            diagnostic = exc.diagnostic_code if isinstance(exc, VideoProviderError) else "local_generation_failure"
            safe_error = (
                str(exc)
                if isinstance(exc, VideoProviderError)
                else "Generation failed during local validation or output verification."
            )
            self._set_state(
                job_id,
                VideoJobState.FAILED,
                "AI video generation failed. See the captured provider error.",
                error_code=code,
                diagnostic_code=diagnostic,
                error=safe_error,
            )

    def get(self, job_id: str | UUID) -> VideoJobResponse:
        try:
            parsed = job_id if isinstance(job_id, UUID) else UUID(str(job_id))
        except (ValueError, TypeError, AttributeError) as exc:
            raise VideoJobNotFoundError("AI video job was not found.") from exc
        with self._lock:
            job = self._jobs.get(parsed)
            if job is None:
                raise VideoJobNotFoundError("AI video job was not found.")
            return job.model_copy(deep=True)

    def output_path(self, job_id: str | UUID) -> Path:
        job = self.get(job_id)
        if job.state != VideoJobState.COMPLETED or not job.output_filename:
            raise VideoJobOutputUnavailableError("AI video output is available only after verified completion.")
        directory = (self.output_dir / str(job.job_id)).resolve()
        path = (directory / job.output_filename).resolve()
        if path.parent != directory or not verify_mp4(path):
            raise VideoJobOutputUnavailableError("Verified AI video output is missing.")
        return path

    def wait(self, job_id: str | UUID, timeout: float = 10.0) -> VideoJobResponse:
        parsed = UUID(str(job_id))
        with self._lock:
            future = self._futures.get(parsed)
        if future is None:
            raise VideoJobNotFoundError("AI video job was not found.")
        future.result(timeout=timeout)
        return self.get(parsed)

    def shutdown(self) -> None:
        self._executor.shutdown(wait=True, cancel_futures=False)
