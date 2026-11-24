from __future__ import annotations

import shutil
import subprocess
import threading
from concurrent.futures import Future, ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable
from uuid import UUID, uuid4

from app.services.render_verifier import verify_mp4
from app.services.timeline.contracts import (
    TimelineExportMetadata,
    TimelineExportProfile,
    TimelineExportResponse,
    TimelineExportState,
    TimelineMediaKind,
    TimelineProjectRecord,
)
from app.services.timeline.media import ProbedMedia, TimelineMediaStore, probe_media
from app.services.timeline.projects import TimelineProjectStore


PROFILE_DIMENSIONS = {
    TimelineExportProfile.HD_720P: (1280, 720),
    TimelineExportProfile.FULL_HD_1080P: (1920, 1080),
}


class TimelineExportError(Exception):
    pass


class TimelineExportNotFound(TimelineExportError):
    pass


class TimelineExportUnavailable(TimelineExportError):
    pass


CommandRunner = Callable[[list[str], int], subprocess.CompletedProcess[str]]
ProbeFunction = Callable[[Path, Path], ProbedMedia]


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def run_command(command: list[str], timeout_seconds: int) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=timeout_seconds,
        shell=False,
        check=False,
    )


class TimelineExportManager:
    def __init__(
        self,
        output_dir: Path,
        projects: TimelineProjectStore,
        media: TimelineMediaStore,
        *,
        ffmpeg: Path | None,
        ffprobe: Path | None,
        runner: CommandRunner = run_command,
        probe: ProbeFunction = probe_media,
    ):
        self.output_dir = output_dir.resolve()
        self.projects = projects
        self.media = media
        self.ffmpeg = ffmpeg
        self.ffprobe = ffprobe
        self.runner = runner
        self.probe = probe
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="timeline-export")
        self._jobs: dict[UUID, TimelineExportResponse] = {}
        self._futures: dict[UUID, Future[None]] = {}
        self._lock = threading.RLock()

    def validate_project(self, project: TimelineProjectRecord) -> float:
        if not project.clips:
            raise TimelineExportError("Add at least one clip before exporting the timeline.")
        total = 0.0
        for clip in project.clips:
            _path, media = self.media.media_path(clip.media_id)
            if media.kind != TimelineMediaKind.CLIP:
                raise TimelineExportError("Timeline clip entries must reference video media.")
            end = clip.trim_end_seconds if clip.trim_end_seconds is not None else media.duration_seconds
            if clip.trim_start_seconds >= media.duration_seconds or end > media.duration_seconds + 0.001:
                raise TimelineExportError("A clip trim range exceeds its source duration.")
            total += end - clip.trim_start_seconds
        for track, expected in (
            (project.voice_track, TimelineMediaKind.VOICE),
            (project.music_track, TimelineMediaKind.MUSIC),
        ):
            if track:
                _path, media = self.media.media_path(track.media_id)
                if media.kind != expected:
                    raise TimelineExportError(f"The {expected.value} track references the wrong media kind.")
        if total <= 0 or total > 3600:
            raise TimelineExportError("Timeline export duration must be greater than zero and no more than one hour.")
        return total

    def submit(self, project_id: str | UUID) -> TimelineExportResponse:
        if not self.ffmpeg or not self.ffprobe:
            raise TimelineExportError("FFmpeg and FFprobe are required for timeline export.")
        project = self.projects.get(project_id)
        self.validate_project(project)
        job_id = uuid4()
        now = utc_now()
        job = TimelineExportResponse(
            job_id=job_id,
            project_id=project.project_id,
            state=TimelineExportState.QUEUED,
            message="Timeline export queued behind any active local export.",
            created_at=now,
            updated_at=now,
        )
        with self._lock:
            self._jobs[job_id] = job
            self._futures[job_id] = self._executor.submit(self._execute, job_id, project)
        return job.model_copy(deep=True)

    def _set_state(
        self,
        job_id: UUID,
        state: TimelineExportState,
        message: str,
        *,
        metadata: TimelineExportMetadata | None = None,
        output_filename: str | None = None,
        error: str | None = None,
    ) -> None:
        with self._lock:
            current = self._jobs[job_id]
            history = [*current.state_history, state] if current.state != state else current.state_history
            self._jobs[job_id] = current.model_copy(
                update={
                    "state": state,
                    "message": message,
                    "updated_at": utc_now(),
                    "state_history": history,
                    "metadata": metadata or current.metadata,
                    "output_filename": output_filename or current.output_filename,
                    "error": error,
                }
            )

    def _run(self, command: list[str], output: Path, stage: str, *, timeout_seconds: int = 1800) -> None:
        try:
            completed = self.runner(command, timeout_seconds)
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise TimelineExportError(f"FFmpeg could not complete the {stage} stage.") from exc
        if completed.returncode != 0 or not output.is_file() or output.stat().st_size == 0:
            raise TimelineExportError(f"FFmpeg failed during the {stage} stage.")

    @staticmethod
    def _video_filter(width: int, height: int) -> str:
        return (
            f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
            f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:black,"
            "fps=30,format=yuv420p,setpts=PTS-STARTPTS"
        )

    def _normalize_command(
        self,
        source: Path,
        destination: Path,
        *,
        start: float,
        duration: float,
        volume: float,
        has_audio: bool,
        width: int,
        height: int,
    ) -> list[str]:
        assert self.ffmpeg is not None
        command = [
            str(self.ffmpeg), "-hide_banner", "-loglevel", "error", "-y",
            "-ss", f"{start:.6f}", "-t", f"{duration:.6f}", "-i", str(source),
        ]
        if has_audio:
            audio_filter = (
                f"[0:a]aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo,"
                f"volume={volume:.4f},asetpts=PTS-STARTPTS[a]"
            )
            filter_complex = f"[0:v]{self._video_filter(width, height)}[v];{audio_filter}"
        else:
            command.extend([
                "-f", "lavfi", "-t", f"{duration:.6f}",
                "-i", "anullsrc=channel_layout=stereo:sample_rate=48000",
            ])
            filter_complex = (
                f"[0:v]{self._video_filter(width, height)}[v];"
                "[1:a]aformat=sample_fmts=fltp:channel_layouts=stereo,asetpts=PTS-STARTPTS[a]"
            )
        command.extend([
            "-filter_complex", filter_complex,
            "-map", "[v]", "-map", "[a]",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "22",
            "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2",
            "-movflags", "+faststart", str(destination),
        ])
        return command

    def _mix_command(
        self,
        project: TimelineProjectRecord,
        joined: Path,
        destination: Path,
        total_duration: float,
    ) -> list[str]:
        assert self.ffmpeg is not None
        command = [str(self.ffmpeg), "-hide_banner", "-loglevel", "error", "-y", "-i", str(joined)]
        filters = ["[0:a]aresample=48000[base]"]
        labels = ["[base]"]
        input_index = 1
        for name, track in (("voice", project.voice_track), ("music", project.music_track)):
            if not track:
                continue
            path, _record = self.media.media_path(track.media_id)
            command.extend(["-i", str(path)])
            delay_ms = round(track.start_seconds * 1000)
            filters.append(
                f"[{input_index}:a]aresample=48000,volume={track.volume:.4f},"
                f"adelay=delays={delay_ms}:all=1,apad,atrim=0:{total_duration:.6f}[{name}]"
            )
            labels.append(f"[{name}]")
            input_index += 1
        filters.append(
            f"{''.join(labels)}amix=inputs={len(labels)}:duration=first:dropout_transition=0:normalize=0,"
            "alimiter=limit=0.95[aout]"
        )
        command.extend([
            "-filter_complex", ";".join(filters),
            "-map", "0:v:0", "-map", "[aout]",
            "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2",
            "-movflags", "+faststart", str(destination),
        ])
        return command

    def _execute(self, job_id: UUID, project: TimelineProjectRecord) -> None:
        directory = (self.output_dir / str(job_id)).resolve()
        try:
            if directory.parent != self.output_dir:
                raise TimelineExportError("Timeline export path escaped its configured directory.")
            directory.mkdir(parents=True, exist_ok=False)
            self._set_state(job_id, TimelineExportState.VALIDATING, "Validating project media and trim ranges.")
            total_duration = self.validate_project(project)
            width, height = PROFILE_DIMENSIONS[project.export_profile]
            normalized: list[Path] = []
            for index, clip in enumerate(project.clips):
                source, record = self.media.media_path(clip.media_id)
                end = clip.trim_end_seconds if clip.trim_end_seconds is not None else record.duration_seconds
                duration = end - clip.trim_start_seconds
                destination = directory / f"normalized-{index:03d}.mp4"
                self._set_state(
                    job_id,
                    TimelineExportState.NORMALIZING,
                    f"Normalizing clip {index + 1} of {len(project.clips)}.",
                )
                command = self._normalize_command(
                    source,
                    destination,
                    start=clip.trim_start_seconds,
                    duration=duration,
                    volume=clip.volume,
                    has_audio=record.has_audio,
                    width=width,
                    height=height,
                )
                self._run(command, destination, f"clip {index + 1} normalization")
                normalized.append(destination)

            concat_file = directory / "concat.txt"
            concat_file.write_text(
                "".join(f"file '{path.name}'\n" for path in normalized),
                encoding="utf-8",
            )
            joined = directory / "joined.mp4"
            self._set_state(job_id, TimelineExportState.CONCATENATING, "Concatenating normalized clips in timeline order.")
            assert self.ffmpeg is not None
            concat_command = [
                str(self.ffmpeg), "-hide_banner", "-loglevel", "error", "-y",
                "-f", "concat", "-safe", "1", "-i", str(concat_file),
                "-c", "copy", "-movflags", "+faststart", str(joined),
            ]
            self._run(concat_command, joined, "clip concatenation")

            final = directory / "timeline-export.mp4"
            if project.voice_track or project.music_track:
                self._set_state(job_id, TimelineExportState.MIXING_AUDIO, "Mixing timeline audio tracks locally.")
                self._run(
                    self._mix_command(project, joined, final, total_duration),
                    final,
                    "audio mixing",
                )
            else:
                shutil.copy2(joined, final)

            self._set_state(job_id, TimelineExportState.VERIFYING, "Verifying the exported MP4 with FFprobe.")
            if not verify_mp4(final) or not self.ffprobe:
                raise TimelineExportError("Exported timeline failed MP4 envelope validation.")
            probed = self.probe(final, self.ffprobe)
            if probed.width != width or probed.height != height or not probed.frame_rate:
                raise TimelineExportError("Exported timeline metadata does not match the selected profile.")
            metadata = TimelineExportMetadata(
                width=probed.width,
                height=probed.height,
                duration_seconds=probed.duration_seconds,
                frame_rate=probed.frame_rate,
                codec=probed.codec,
            )
            self._set_state(
                job_id,
                TimelineExportState.COMPLETED,
                "Timeline export passed independent MP4 and FFprobe validation.",
                metadata=metadata,
                output_filename=final.name,
            )
        except Exception as exc:
            safe_error = str(exc) if isinstance(exc, TimelineExportError) else "Timeline export failed during local processing."
            self._set_state(
                job_id,
                TimelineExportState.FAILED,
                "Timeline export failed at the reported local processing stage.",
                error=safe_error,
            )

    def get(self, job_id: str | UUID) -> TimelineExportResponse:
        try:
            parsed = job_id if isinstance(job_id, UUID) else UUID(str(job_id))
        except (ValueError, TypeError, AttributeError) as exc:
            raise TimelineExportNotFound("Timeline export job was not found.") from exc
        with self._lock:
            job = self._jobs.get(parsed)
            if not job:
                raise TimelineExportNotFound("Timeline export job was not found.")
            return job.model_copy(deep=True)

    def output_path(self, job_id: str | UUID) -> Path:
        job = self.get(job_id)
        if job.state != TimelineExportState.COMPLETED or not job.output_filename:
            raise TimelineExportUnavailable("Timeline output is available only after verified completion.")
        directory = (self.output_dir / str(job.job_id)).resolve()
        output = (directory / job.output_filename).resolve()
        if output.parent != directory or not verify_mp4(output):
            raise TimelineExportUnavailable("Verified timeline output is missing or unsafe.")
        return output

    def wait(self, job_id: str | UUID, timeout: float = 60.0) -> TimelineExportResponse:
        parsed = UUID(str(job_id))
        with self._lock:
            future = self._futures.get(parsed)
        if not future:
            raise TimelineExportNotFound("Timeline export job was not found.")
        future.result(timeout=timeout)
        return self.get(parsed)

    def shutdown(self) -> None:
        self._executor.shutdown(wait=True, cancel_futures=False)
