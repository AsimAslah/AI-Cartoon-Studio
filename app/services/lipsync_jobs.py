"""Provider-neutral background jobs for genuine lip-sync inference.

No production provider is enabled by default. Tests inject a deterministic fake
provider to verify lifecycle behavior without claiming AI inference occurred.
"""

from __future__ import annotations

import threading
from concurrent.futures import Future, ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol
from uuid import UUID, uuid4

from app.services.lipsync_contract import (
    LipSyncJobRequest,
    LipSyncJobResponse,
    LipSyncJobState,
    LipSyncUploadRecord,
    ProviderCapabilities,
    ProviderUnavailableError,
)
from app.services.render_verifier import verify_mp4


class LipSyncJobError(Exception):
    pass


class LipSyncJobNotFoundError(LipSyncJobError):
    pass


class LipSyncOutputUnavailableError(LipSyncJobError):
    pass


class LipSyncRuntimeProvider(Protocol):
    def capabilities(self) -> ProviderCapabilities: ...

    def generate(
        self,
        upload: LipSyncUploadRecord,
        source_path: Path,
        audio_path: Path,
        output_dir: Path,
    ) -> Path: ...


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class LipSyncJobManager:
    def __init__(self, output_dir: Path, providers: dict[str, LipSyncRuntimeProvider] | None = None):
        self.output_dir = output_dir.resolve()
        self.providers = providers or {}
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="lipsync-inference")
        self._jobs: dict[UUID, LipSyncJobResponse] = {}
        self._futures: dict[UUID, Future[None]] = {}
        self._lock = threading.RLock()

    def submit(
        self,
        request: LipSyncJobRequest,
        upload: LipSyncUploadRecord,
        source_path: Path,
        audio_path: Path,
    ) -> LipSyncJobResponse:
        provider = self.providers.get(request.provider_id)
        if provider is None:
            raise ProviderUnavailableError(
                "Selected lip-sync provider is unavailable. No job was created, no video was generated, and no API was charged."
            )
        capabilities = provider.capabilities()
        if not capabilities.configured or not capabilities.performs_real_lipsync:
            raise ProviderUnavailableError(
                "Selected lip-sync provider is not configured for real inference. No job was created and no API was charged."
            )
        if upload.request.mode not in capabilities.modes:
            raise ProviderUnavailableError(f"{capabilities.name} does not support {upload.request.mode.value} input.")

        job_id = uuid4()
        now = utc_now()
        job = LipSyncJobResponse(
            job_id=job_id,
            upload_id=upload.upload_id,
            provider_id=request.provider_id,
            state=LipSyncJobState.QUEUED,
            message="Lip-sync job queued behind any active inference job.",
            created_at=now,
            updated_at=now,
        )
        with self._lock:
            self._jobs[job_id] = job
            self._futures[job_id] = self._executor.submit(
                self._execute, job_id, provider, upload, source_path, audio_path
            )
        return job.model_copy(deep=True)

    def _set_state(
        self,
        job_id: UUID,
        state: LipSyncJobState,
        message: str,
        *,
        output_filename: str | None = None,
        error: str | None = None,
    ) -> None:
        with self._lock:
            current = self._jobs[job_id]
            self._jobs[job_id] = current.model_copy(
                update={
                    "state": state,
                    "message": message,
                    "updated_at": utc_now(),
                    "state_history": [*current.state_history, state],
                    "output_filename": output_filename,
                    "error": error,
                }
            )

    def _execute(
        self,
        job_id: UUID,
        provider: LipSyncRuntimeProvider,
        upload: LipSyncUploadRecord,
        source_path: Path,
        audio_path: Path,
    ) -> None:
        directory = (self.output_dir / str(job_id)).resolve()
        try:
            if directory.parent != self.output_dir:
                raise LipSyncJobError("Job output path escaped the configured output directory.")
            self._set_state(job_id, LipSyncJobState.PREPARING, "Preparing validated media for the provider.")
            directory.mkdir(parents=True, exist_ok=False)
            self._set_state(job_id, LipSyncJobState.SUBMITTING, "Submitting media to the selected provider.")
            self._set_state(job_id, LipSyncJobState.PROCESSING, "The provider is performing lip-sync inference.")
            output = provider.generate(upload, source_path, audio_path, directory).resolve()
            self._set_state(job_id, LipSyncJobState.VERIFYING, "Verifying the returned MP4 output.")
            if output.parent != directory or not verify_mp4(output):
                raise LipSyncJobError("Provider output was missing, unsafe, or not a valid MP4 envelope.")
            self._set_state(
                job_id,
                LipSyncJobState.COMPLETED,
                "Real provider output completed and passed MP4 validation.",
                output_filename=output.name,
            )
        except Exception as exc:
            self._set_state(
                job_id,
                LipSyncJobState.FAILED,
                "Lip-sync inference failed. See the captured error.",
                error=str(exc),
            )

    def get(self, job_id: str | UUID) -> LipSyncJobResponse:
        try:
            parsed = job_id if isinstance(job_id, UUID) else UUID(str(job_id))
        except (ValueError, TypeError, AttributeError) as exc:
            raise LipSyncJobNotFoundError("Lip-sync job was not found.") from exc
        with self._lock:
            job = self._jobs.get(parsed)
            if job is None:
                raise LipSyncJobNotFoundError("Lip-sync job was not found.")
            return job.model_copy(deep=True)

    def output_path(self, job_id: str | UUID) -> Path:
        job = self.get(job_id)
        if job.state != LipSyncJobState.COMPLETED or not job.output_filename:
            raise LipSyncOutputUnavailableError("Lip-sync output is available only after verified completion.")
        directory = (self.output_dir / str(job.job_id)).resolve()
        path = (directory / job.output_filename).resolve()
        if path.parent != directory or not verify_mp4(path):
            raise LipSyncOutputUnavailableError("Verified lip-sync output is missing.")
        return path

    def wait(self, job_id: str | UUID, timeout: float = 10.0) -> LipSyncJobResponse:
        parsed = UUID(str(job_id))
        with self._lock:
            future = self._futures.get(parsed)
        if future is None:
            raise LipSyncJobNotFoundError("Lip-sync job was not found.")
        future.result(timeout=timeout)
        return self.get(parsed)

    def shutdown(self) -> None:
        self._executor.shutdown(wait=True, cancel_futures=False)
