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
    TimelineClip,
    TimelineExportMetadata,
    TimelineExportProfile,
    TimelineExportResponse,
    TimelineExportState,
    TimelineMediaKind,
    TimelineProjectRecord,
    TimelineSceneType,
    TimelineTextAnimation,
    TimelineTextPosition,
    TimelineTransition,
)
from app.services.timeline.media import ProbedMedia, TimelineMediaStore, probe_media
from app.services.timeline.projects import TimelineProjectStore


PROFILE_DIMENSIONS = {
    TimelineExportProfile.HD_720P: (1280, 720),
    TimelineExportProfile.FULL_HD_1080P: (1920, 1080),
}

IMAGE_MEDIA_KINDS = {
    TimelineMediaKind.IMAGE,
    TimelineMediaKind.LOGO,
    TimelineMediaKind.CHARACTER_REFERENCE,
}

TRANSITION_FILTERS = {
    TimelineTransition.CROSSFADE: "fade",
    TimelineTransition.FADE_BLACK: "fadeblack",
    TimelineTransition.FADE_WHITE: "fadewhite",
    TimelineTransition.DISSOLVE: "dissolve",
    TimelineTransition.SLIDE_LEFT: "slideleft",
    TimelineTransition.SLIDE_RIGHT: "slideright",
    TimelineTransition.ZOOM: "zoomin",
}


def discover_safe_font() -> Path | None:
    candidates = (
        Path("C:/Windows/Fonts/Nirmala.ttc"),
        Path("C:/Windows/Fonts/arial.ttf"),
        Path("C:/Windows/Fonts/segoeui.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    )
    return next((candidate.resolve() for candidate in candidates if candidate.is_file()), None)


def _filter_path(path: Path) -> str:
    return str(path.resolve()).replace("\\", "/").replace(":", r"\:").replace("'", r"\'")


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
        font_path: Path | None = None,
    ):
        self.output_dir = output_dir.resolve()
        self.projects = projects
        self.media = media
        self.ffmpeg = ffmpeg
        self.ffprobe = ffprobe
        self.runner = runner
        self.probe = probe
        self.font_path = font_path or discover_safe_font()
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="timeline-export")
        self._jobs: dict[UUID, TimelineExportResponse] = {}
        self._futures: dict[UUID, Future[None]] = {}
        self._lock = threading.RLock()

    @staticmethod
    def _clip_duration(clip: TimelineClip, media_record=None) -> float:
        if clip.scene_type in {
            TimelineSceneType.STILL,
            TimelineSceneType.TITLE_CARD,
            TimelineSceneType.BRANDING_CARD,
        }:
            return clip.duration_seconds
        if media_record is None:
            raise TimelineExportError("A video scene has no assigned media.")
        end = clip.trim_end_seconds if clip.trim_end_seconds is not None else media_record.duration_seconds
        return end - clip.trim_start_seconds

    def validate_project(self, project: TimelineProjectRecord) -> float:
        if not project.clips:
            raise TimelineExportError("Add at least one clip before exporting the timeline.")
        durations: list[float] = []
        for index, clip in enumerate(project.clips):
            media = None
            if clip.scene_type in {TimelineSceneType.TITLE_CARD, TimelineSceneType.BRANDING_CARD}:
                if clip.media_id is not None:
                    raise TimelineExportError("Title and branding cards cannot use a primary media file.")
                if not self.font_path:
                    raise TimelineExportError("A trusted local font is required to render title cards.")
            else:
                if clip.media_id is None:
                    label = clip.slot_title or f"scene {index + 1}"
                    raise TimelineExportError(f"Assign actual media to {label} before export.")
                _path, media = self.media.media_path(clip.media_id)
                expected = TimelineMediaKind.CLIP if clip.scene_type == TimelineSceneType.VIDEO else TimelineMediaKind.IMAGE
                if media.kind != expected:
                    raise TimelineExportError(f"{clip.scene_type.value.capitalize()} scenes reference the wrong media kind.")
                if clip.scene_type == TimelineSceneType.VIDEO:
                    end = clip.trim_end_seconds if clip.trim_end_seconds is not None else media.duration_seconds
                    if clip.trim_start_seconds >= media.duration_seconds or end > media.duration_seconds + 0.001:
                        raise TimelineExportError("A clip trim range exceeds its source duration.")
            if (clip.title_text or clip.overlay_text) and not self.font_path:
                raise TimelineExportError("A trusted local font is required to render text overlays.")
            if clip.logo_media_id:
                _logo_path, logo = self.media.media_path(clip.logo_media_id)
                if logo.kind not in {TimelineMediaKind.LOGO, TimelineMediaKind.IMAGE}:
                    raise TimelineExportError("Logo overlays must reference a validated logo image.")
            if clip.lut_media_id:
                _lut_path, lut = self.media.media_path(clip.lut_media_id)
                if lut.kind != TimelineMediaKind.LUT:
                    raise TimelineExportError("Color effects must reference a validated .cube LUT.")
            duration = self._clip_duration(clip, media)
            if duration <= 0:
                raise TimelineExportError("Every scene must have a positive configured duration.")
            if clip.fade_in_seconds > duration or clip.fade_out_seconds > duration:
                raise TimelineExportError("Scene fades cannot exceed the scene duration.")
            if clip.logo_fade_in_seconds > duration or clip.logo_fade_out_seconds > duration:
                raise TimelineExportError("Logo fades cannot exceed the scene duration.")
            durations.append(duration)

        total = sum(durations)
        for index, clip in enumerate(project.clips[:-1]):
            if clip.transition_to_next != TimelineTransition.CUT:
                transition = clip.transition_duration_seconds
                if transition >= min(durations[index], durations[index + 1]):
                    raise TimelineExportError("Crossfade duration must be shorter than both adjacent scenes.")
                total -= transition
        if project.clips[-1].transition_to_next != TimelineTransition.CUT:
            raise TimelineExportError("The final scene cannot transition to a scene that does not exist.")
        for track, expected in (
            (project.voice_track, TimelineMediaKind.VOICE),
            (project.music_track, TimelineMediaKind.MUSIC),
        ):
            if track:
                _path, media = self.media.media_path(track.media_id)
                if media.kind != expected:
                    raise TimelineExportError(f"The {expected.value} track references the wrong media kind.")
                effective_start = track.start_seconds + track.sync_offset_seconds
                if effective_start >= total:
                    raise TimelineExportError(f"The {expected.value} track starts after the timeline ends.")
                source_end = track.source_end_seconds if track.source_end_seconds is not None else media.duration_seconds
                if track.source_start_seconds >= media.duration_seconds or source_end > media.duration_seconds + 0.001:
                    raise TimelineExportError(f"The {expected.value} source markers exceed the audio duration.")
                audible = source_end - track.source_start_seconds
                if track.end_seconds is not None:
                    if track.end_seconds > total + 0.001:
                        raise TimelineExportError(f"The {expected.value} timeline end exceeds the project duration.")
                    audible = min(audible, track.end_seconds - effective_start)
                audible = min(audible, total - effective_start)
                if audible <= 0:
                    raise TimelineExportError(f"The {expected.value} track has no audible range.")
                if track.fade_in_seconds > audible or track.fade_out_seconds > audible:
                    raise TimelineExportError(f"The {expected.value} fades exceed its audible duration.")
        if total <= 0 or total > 3600:
            raise TimelineExportError("Timeline export duration must be greater than zero and no more than one hour.")
        return total

    def submit(self, project_id: str | UUID) -> TimelineExportResponse:
        if not self.ffmpeg or not self.ffprobe:
            raise TimelineExportError("FFmpeg and FFprobe are required for timeline export.")
        project = self.projects.get(project_id)
        self.validate_project(project)
        with self._lock:
            for existing in self._jobs.values():
                if (
                    existing.project_id == project.project_id
                    and existing.state not in {TimelineExportState.COMPLETED, TimelineExportState.FAILED}
                ):
                    return existing.model_copy(
                        update={"message": "An export for this saved project is already active."},
                        deep=True,
                    )
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
    def _cleanup_intermediates(directory: Path) -> None:
        if not directory.is_dir():
            return
        candidates = [directory / "concat.txt", directory / "joined.mp4"]
        for pattern in ("normalized-*.mp4", "title-*.txt", "overlay-*.txt"):
            candidates.extend(directory.glob(pattern))
        for path in candidates:
            resolved = path.resolve()
            if resolved.parent == directory and resolved.is_file():
                resolved.unlink()

    @staticmethod
    def _video_filter(width: int, height: int) -> str:
        return (
            f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
            f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:black,"
            "fps=30,format=yuv420p,setpts=PTS-STARTPTS"
        )

    def _drawtext_filter(self, text_file: Path, clip: TimelineClip, *, title: bool) -> str:
        if not self.font_path:
            raise TimelineExportError("A trusted local font is required to render text.")
        positions = {
            TimelineTextPosition.TOP: ("(w-text_w)/2", "h*0.10"),
            TimelineTextPosition.CENTER: ("(w-text_w)/2", "(h-text_h)/2"),
            TimelineTextPosition.LOWER_THIRD: ("(w-text_w)/2", "h*0.72"),
            TimelineTextPosition.CUSTOM: (
                f"w*{clip.text_x:.4f}-text_w/2",
                f"h*{clip.text_y:.4f}-text_h/2",
            ),
        }
        x_position, y_position = positions[clip.text_position]
        animation_duration = clip.text_animation_duration_seconds
        alpha = "1"
        if clip.text_animation == TimelineTextAnimation.FADE:
            alpha = f"min(t/{animation_duration:.4f}\\,1)"
        elif clip.text_animation == TimelineTextAnimation.SLIDE_UP:
            target = y_position
            y_position = f"h-(h-({target}))*min(t/{animation_duration:.4f}\\,1)"
        elif clip.text_animation == TimelineTextAnimation.SLIDE_LEFT:
            target = x_position
            x_position = f"w-(w-({target}))*min(t/{animation_duration:.4f}\\,1)"
        size = min(96, clip.font_size + 12) if title else clip.font_size
        return (
            f"drawtext=fontfile='{_filter_path(self.font_path)}':"
            f"textfile='{_filter_path(text_file)}':reload=0:expansion=none:fontcolor=white:fontsize={size}:"
            f"x={x_position}:y={y_position}:alpha='{alpha}':"
            "box=1:boxcolor=black@0.55:boxborderw=16"
        )

    def _normalize_command(
        self,
        source: Path | None,
        destination: Path,
        *,
        clip: TimelineClip,
        start: float,
        duration: float,
        has_audio: bool,
        width: int,
        height: int,
        title_file: Path | None = None,
        overlay_file: Path | None = None,
        logo_path: Path | None = None,
        lut_path: Path | None = None,
    ) -> list[str]:
        assert self.ffmpeg is not None
        command = [str(self.ffmpeg), "-hide_banner", "-loglevel", "error", "-y"]
        if clip.scene_type in {TimelineSceneType.TITLE_CARD, TimelineSceneType.BRANDING_CARD}:
            command.extend([
                "-f", "lavfi", "-t", f"{duration:.6f}", "-i",
                f"color=c=0x111318:s={width}x{height}:r=30",
            ])
        elif clip.scene_type == TimelineSceneType.STILL:
            assert source is not None
            command.extend(["-loop", "1", "-t", f"{duration:.6f}", "-i", str(source)])
        else:
            assert source is not None
            command.extend(["-ss", f"{start:.6f}", "-t", f"{duration:.6f}", "-i", str(source)])

        audio_index = 0
        if has_audio:
            audio_filter = (
                f"[0:a]aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo,"
                f"volume={clip.volume:.4f},apad,atrim=0:{duration:.6f},asetpts=PTS-STARTPTS"
            )
        else:
            audio_index = 1
            command.extend([
                "-f", "lavfi", "-t", f"{duration:.6f}",
                "-i", "anullsrc=channel_layout=stereo:sample_rate=48000",
            ])
            audio_filter = (
                f"[{audio_index}:a]aformat=sample_fmts=fltp:channel_layouts=stereo,"
                f"atrim=0:{duration:.6f},asetpts=PTS-STARTPTS"
            )

        logo_index: int | None = None
        if logo_path:
            logo_index = audio_index + 1 if not has_audio else 1
            command.extend(["-loop", "1", "-i", str(logo_path)])

        video_filters = [self._video_filter(width, height)]
        if clip.brightness != 0 or clip.contrast != 1 or clip.saturation != 1:
            video_filters.append(
                f"eq=brightness={clip.brightness:.4f}:contrast={clip.contrast:.4f}:saturation={clip.saturation:.4f}"
            )
        if clip.exposure != 0:
            video_filters.append(f"exposure=exposure={clip.exposure:.4f}")
        if clip.color_temperature != 0:
            temperature = round(6500 + clip.color_temperature * 3500)
            video_filters.append(f"colortemperature=temperature={temperature}")
        if lut_path:
            video_filters.append(f"lut3d=file='{_filter_path(lut_path)}'")
        if clip.fade_in_seconds:
            video_filters.append(f"fade=t=in:st=0:d={clip.fade_in_seconds:.6f}")
        if clip.fade_out_seconds:
            video_filters.append(
                f"fade=t=out:st={max(0.0, duration - clip.fade_out_seconds):.6f}:d={clip.fade_out_seconds:.6f}"
            )
        if title_file:
            video_filters.append(self._drawtext_filter(title_file, clip, title=True))
        if overlay_file:
            video_filters.append(self._drawtext_filter(overlay_file, clip, title=False))

        audio_chain = audio_filter
        if clip.fade_in_seconds:
            audio_chain += f",afade=t=in:st=0:d={clip.fade_in_seconds:.6f}"
        if clip.fade_out_seconds:
            audio_chain += (
                f",afade=t=out:st={max(0.0, duration - clip.fade_out_seconds):.6f}:d={clip.fade_out_seconds:.6f}"
            )

        filters = [f"[0:v]{','.join(video_filters)}[basev]"]
        if logo_index is not None:
            logo_width = max(96, round(width * 0.18))
            logo_filters = [f"scale={logo_width}:-1", "format=rgba"]
            if clip.logo_fade_in_seconds:
                logo_filters.append(f"fade=t=in:st=0:d={clip.logo_fade_in_seconds:.6f}:alpha=1")
            if clip.logo_fade_out_seconds:
                logo_filters.append(
                    f"fade=t=out:st={max(0.0, duration - clip.logo_fade_out_seconds):.6f}:"
                    f"d={clip.logo_fade_out_seconds:.6f}:alpha=1"
                )
            filters.extend([
                f"[{logo_index}:v]{','.join(logo_filters)}[logo]",
                "[basev][logo]overlay=x=W-w-32:y=H-h-32:shortest=1[v]",
            ])
        else:
            filters.append("[basev]null[v]")
        filters.append(f"{audio_chain}[a]")
        command.extend([
            "-filter_complex", ";".join(filters),
            "-map", "[v]", "-map", "[a]",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "22",
            "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2",
            "-t", f"{duration:.6f}",
            "-movflags", "+faststart", str(destination),
        ])
        return command

    def _transition_command(
        self,
        project: TimelineProjectRecord,
        normalized: list[Path],
        durations: list[float],
        destination: Path,
    ) -> list[str]:
        assert self.ffmpeg is not None
        command = [str(self.ffmpeg), "-hide_banner", "-loglevel", "error", "-y"]
        for path in normalized:
            command.extend(["-i", str(path)])
        filters: list[str] = []
        for index in range(len(normalized)):
            filters.extend([
                f"[{index}:v]settb=AVTB,setpts=PTS-STARTPTS[v{index}]",
                f"[{index}:a]aresample=48000,asetpts=PTS-STARTPTS[a{index}]",
            ])
        video_label = "v0"
        audio_label = "a0"
        elapsed = durations[0]
        for index in range(1, len(normalized)):
            prior = project.clips[index - 1]
            next_video = f"vx{index}"
            next_audio = f"ax{index}"
            if prior.transition_to_next != TimelineTransition.CUT:
                transition = prior.transition_duration_seconds
                offset = elapsed - transition
                transition_filter = TRANSITION_FILTERS[prior.transition_to_next]
                filters.extend([
                    f"[{video_label}][v{index}]xfade=transition={transition_filter}:"
                    f"duration={transition:.6f}:offset={offset:.6f}[{next_video}]",
                    f"[{audio_label}][a{index}]acrossfade=d={transition:.6f}:c1=tri:c2=tri[{next_audio}]",
                ])
                elapsed += durations[index] - transition
            else:
                filters.extend([
                    f"[{video_label}][v{index}]concat=n=2:v=1:a=0[{next_video}]",
                    f"[{audio_label}][a{index}]concat=n=2:v=0:a=1[{next_audio}]",
                ])
                elapsed += durations[index]
            video_label, audio_label = next_video, next_audio
        command.extend([
            "-filter_complex", ";".join(filters),
            "-map", f"[{video_label}]", "-map", f"[{audio_label}]",
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
        input_index = 1
        track_labels: dict[str, str] = {}
        for name, track in (("voice", project.voice_track), ("music", project.music_track)):
            if not track:
                continue
            path, record = self.media.media_path(track.media_id)
            command.extend(["-i", str(path)])
            effective_start = track.start_seconds + track.sync_offset_seconds
            source_end = track.source_end_seconds if track.source_end_seconds is not None else record.duration_seconds
            audible = min(source_end - track.source_start_seconds, total_duration - effective_start)
            if track.end_seconds is not None:
                audible = min(audible, track.end_seconds - effective_start)
            source_end = track.source_start_seconds + audible
            delay_ms = round(effective_start * 1000)
            chain = (
                f"[{input_index}:a]atrim=start={track.source_start_seconds:.6f}:end={source_end:.6f},"
                "asetpts=PTS-STARTPTS,aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo,"
                f"volume={track.volume:.4f}"
            )
            if track.fade_in_seconds:
                chain += f",afade=t=in:st=0:d={track.fade_in_seconds:.6f}"
            if track.fade_out_seconds:
                chain += (
                    f",afade=t=out:st={max(0.0, audible - track.fade_out_seconds):.6f}:"
                    f"d={track.fade_out_seconds:.6f}"
                )
            chain += (
                f",adelay=delays={delay_ms}:all=1,apad,atrim=0:{total_duration:.6f}[{name}_raw]"
            )
            filters.append(chain)
            track_labels[name] = f"[{name}_raw]"
            input_index += 1

        labels = ["[base]"]
        if "voice" in track_labels and "music" in track_labels and project.ducking_enabled and project.ducking_intensity > 0:
            ratio = 2 + 18 * project.ducking_intensity
            filters.extend([
                f"{track_labels['voice']}asplit=2[voice_mix][voice_side]",
                f"{track_labels['music']}[voice_side]sidechaincompress=threshold=0.04:ratio={ratio:.4f}:"
                "attack=20:release=350[ducked_music]",
            ])
            labels.extend(["[voice_mix]", "[ducked_music]"])
        else:
            if "voice" in track_labels:
                labels.append(track_labels["voice"])
            if "music" in track_labels:
                labels.append(track_labels["music"])
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
            durations: list[float] = []
            for index, clip in enumerate(project.clips):
                source = None
                record = None
                if clip.media_id is not None:
                    source, record = self.media.media_path(clip.media_id)
                duration = self._clip_duration(clip, record)
                title_file = None
                overlay_file = None
                if clip.title_text:
                    title_file = directory / f"title-{index:03d}.txt"
                    title_file.write_text(clip.title_text, encoding="utf-8")
                if clip.overlay_text:
                    overlay_file = directory / f"overlay-{index:03d}.txt"
                    overlay_file.write_text(clip.overlay_text, encoding="utf-8")
                logo_path = None
                if clip.logo_media_id:
                    logo_path, _logo_record = self.media.media_path(clip.logo_media_id)
                lut_path = None
                if clip.lut_media_id:
                    lut_path, _lut_record = self.media.media_path(clip.lut_media_id)
                destination = directory / f"normalized-{index:03d}.mp4"
                self._set_state(
                    job_id,
                    TimelineExportState.NORMALIZING,
                    f"Normalizing clip {index + 1} of {len(project.clips)}.",
                )
                command = self._normalize_command(
                    source,
                    destination,
                    clip=clip,
                    start=clip.trim_start_seconds,
                    duration=duration,
                    has_audio=bool(record and record.has_audio and clip.scene_type == TimelineSceneType.VIDEO),
                    width=width,
                    height=height,
                    title_file=title_file,
                    overlay_file=overlay_file,
                    logo_path=logo_path,
                    lut_path=lut_path,
                )
                self._run(command, destination, f"clip {index + 1} normalization")
                normalized.append(destination)
                durations.append(duration)

            concat_file = directory / "concat.txt"
            concat_file.write_text(
                "".join(f"file '{path.name}'\n" for path in normalized),
                encoding="utf-8",
            )
            joined = directory / "joined.mp4"
            self._set_state(job_id, TimelineExportState.CONCATENATING, "Concatenating normalized clips in timeline order.")
            assert self.ffmpeg is not None
            if any(clip.transition_to_next != TimelineTransition.CUT for clip in project.clips[:-1]):
                concat_command = self._transition_command(project, normalized, durations, joined)
            else:
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
        finally:
            self._cleanup_intermediates(directory)

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
