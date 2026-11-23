from __future__ import annotations

import threading
from concurrent.futures import Future, ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable
from uuid import UUID, uuid4

from app.models import RenderJobResponse, RenderState, StoryboardDocument, StoryboardScene
from app.services.blender_runner import BlenderRunResult
from app.services.render_verifier import verify_mp4, verify_png

Renderer = Callable[[StoryboardScene, Path], BlenderRunResult]


class RenderJobError(Exception):
    pass


class RenderJobNotFoundError(RenderJobError):
    pass


class UnsupportedStoryboardRenderError(RenderJobError):
    pass


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class RenderJobManager:
    def __init__(self, jobs_dir: Path, renderer: Renderer, *, max_workers: int = 1):
        self.jobs_dir = jobs_dir.resolve()
        self.renderer = renderer
        self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="cartoon-render")
        self._jobs: dict[UUID, RenderJobResponse] = {}
        self._futures: dict[UUID, Future[None]] = {}
        self._lock = threading.RLock()

    def submit(self, storyboard: StoryboardDocument) -> RenderJobResponse:
        scenes = storyboard.ordered_scenes()
        if len(scenes) != 1:
            raise UnsupportedStoryboardRenderError(
                "Rendering currently supports exactly one scene. Save multi-scene projects now; sequencing is planned."
            )
        if scenes[0].duration_seconds > 10:
            raise UnsupportedStoryboardRenderError(
                "Laptop preview renders support scene durations from 1 to 10 seconds. Shorten this scene before rendering."
            )
        job_id = uuid4()
        now = utc_now()
        job = RenderJobResponse(
            job_id=job_id,
            state=RenderState.QUEUED,
            message="Render queued behind any active laptop render.",
            created_at=now,
            updated_at=now,
            scene_count=1,
        )
        with self._lock:
            self._jobs[job_id] = job
            self._futures[job_id] = self._executor.submit(self._execute, job_id, scenes[0])
        return job.model_copy(deep=True)

    def _set_state(
        self,
        job_id: UUID,
        state: RenderState,
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

    def _execute(self, job_id: UUID, scene: StoryboardScene) -> None:
        output_dir = self.jobs_dir / str(job_id)
        try:
            self._set_state(job_id, RenderState.PREPARING, "Validating scene and preparing an isolated output directory.")
            output_dir.mkdir(parents=True, exist_ok=False)
            self._set_state(job_id, RenderState.STARTING_BLENDER, "Starting Blender in background mode.")
            self._set_state(job_id, RenderState.RENDERING, f"Blender is rendering the '{scene.action}' scene.")
            result = self.renderer(scene, output_dir)
            self._set_state(job_id, RenderState.FINALIZING, "Verifying Blender, PNG, and MP4 outputs.")
            preview = output_dir / "preview.png"
            video = output_dir / "first_cartoon.mp4"
            if not result.succeeded or not verify_png(preview) or not verify_mp4(video):
                detail = (result.stderr or result.stdout or "Expected output verification failed.")[-2_000:]
                raise RenderJobError(detail)
            self._set_state(
                job_id,
                RenderState.COMPLETED,
                "Render completed and the MP4 passed validation.",
                output_filename=video.name,
            )
        except Exception as exc:
            self._set_state(job_id, RenderState.FAILED, "Render failed. See the captured error.", error=str(exc))

    def get(self, job_id: str | UUID) -> RenderJobResponse:
        try:
            parsed = job_id if isinstance(job_id, UUID) else UUID(str(job_id))
        except (ValueError, TypeError, AttributeError) as exc:
            raise RenderJobNotFoundError("Render job was not found.") from exc
        with self._lock:
            job = self._jobs.get(parsed)
            if job is None:
                raise RenderJobNotFoundError("Render job was not found.")
            return job.model_copy(deep=True)

    def output_path(self, job_id: str | UUID) -> Path:
        job = self.get(job_id)
        if job.state != RenderState.COMPLETED or not job.output_filename:
            raise RenderJobError("Render output is available only after successful completion.")
        path = (self.jobs_dir / str(job.job_id) / job.output_filename).resolve()
        expected_parent = (self.jobs_dir / str(job.job_id)).resolve()
        if path.parent != expected_parent or not verify_mp4(path):
            raise RenderJobError("Validated render output is missing.")
        return path

    def wait(self, job_id: str | UUID, timeout: float = 10.0) -> RenderJobResponse:
        parsed = UUID(str(job_id))
        with self._lock:
            future = self._futures.get(parsed)
        if future is None:
            raise RenderJobNotFoundError("Render job was not found.")
        future.result(timeout=timeout)
        return self.get(parsed)

    def shutdown(self) -> None:
        self._executor.shutdown(wait=True, cancel_futures=False)
