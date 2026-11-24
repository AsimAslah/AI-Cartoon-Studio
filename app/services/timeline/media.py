from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Callable
from uuid import UUID, uuid4

from pydantic import ValidationError

from app.services.timeline.contracts import TimelineMediaKind, TimelineMediaRecord


MAX_MEDIA_BYTES = {
    TimelineMediaKind.CLIP: 500 * 1024 * 1024,
    TimelineMediaKind.VOICE: 100 * 1024 * 1024,
    TimelineMediaKind.MUSIC: 100 * 1024 * 1024,
    TimelineMediaKind.IMAGE: 25 * 1024 * 1024,
    TimelineMediaKind.LOGO: 25 * 1024 * 1024,
    TimelineMediaKind.CHARACTER_REFERENCE: 25 * 1024 * 1024,
}
IMAGE_KINDS = {
    TimelineMediaKind.IMAGE,
    TimelineMediaKind.LOGO,
    TimelineMediaKind.CHARACTER_REFERENCE,
}
ALLOWED_SUFFIXES = {
    TimelineMediaKind.CLIP: {".mp4"},
    TimelineMediaKind.VOICE: {".wav", ".mp3", ".m4a"},
    TimelineMediaKind.MUSIC: {".wav", ".mp3", ".m4a"},
    TimelineMediaKind.IMAGE: {".png", ".jpg", ".jpeg", ".webp"},
    TimelineMediaKind.LOGO: {".png", ".jpg", ".jpeg", ".webp"},
    TimelineMediaKind.CHARACTER_REFERENCE: {".png", ".jpg", ".jpeg", ".webp"},
}
CONTENT_TYPES = {
    ".mp4": "video/mp4",
    ".wav": "audio/wav",
    ".mp3": "audio/mpeg",
    ".m4a": "audio/mp4",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
}


class TimelineMediaError(Exception):
    pass


class InvalidTimelineMediaId(TimelineMediaError):
    pass


class TimelineMediaNotFound(TimelineMediaError):
    pass


class CorruptTimelineMedia(TimelineMediaError):
    pass


@dataclass(frozen=True)
class ProbedMedia:
    duration_seconds: float
    width: int | None
    height: int | None
    frame_rate: float | None
    codec: str
    has_audio: bool


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def discover_binary(name: str, configured_path: str | None = None) -> Path | None:
    if configured_path:
        candidate = Path(configured_path).expanduser()
        return candidate.resolve() if candidate.is_file() else None
    found = shutil.which(name)
    return Path(found).resolve() if found else None


def _rate(value: str | None) -> float | None:
    if not value or value == "0/0":
        return None
    numerator, separator, denominator = value.partition("/")
    try:
        if separator:
            divisor = float(denominator)
            return float(numerator) / divisor if divisor else None
        return float(value)
    except ValueError:
        return None


def probe_media(path: Path, ffprobe: Path, *, timeout_seconds: int = 30) -> ProbedMedia:
    command = [
        str(ffprobe), "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)
    ]
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            shell=False,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise TimelineMediaError("FFprobe could not inspect the media file.") from exc
    if completed.returncode != 0:
        raise TimelineMediaError("FFprobe rejected the media file.")
    try:
        payload = json.loads(completed.stdout)
        streams = payload.get("streams", [])
        video = next((stream for stream in streams if stream.get("codec_type") == "video"), None)
        audio = next((stream for stream in streams if stream.get("codec_type") == "audio"), None)
        duration_value = payload.get("format", {}).get("duration")
        duration = float(duration_value) if duration_value is not None else 0.0
        if duration < 0:
            raise ValueError
        return ProbedMedia(
            duration_seconds=duration,
            width=int(video["width"]) if video else None,
            height=int(video["height"]) if video else None,
            frame_rate=_rate(video.get("avg_frame_rate")) if video else None,
            codec=str(video["codec_name"] if video else audio["codec_name"]),
            has_audio=audio is not None,
        )
    except (KeyError, StopIteration, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise TimelineMediaError("FFprobe returned incomplete media metadata.") from exc


def create_thumbnail(source: Path, destination: Path, ffmpeg: Path, *, timeout_seconds: int = 60) -> None:
    command = [
        str(ffmpeg), "-hide_banner", "-loglevel", "error", "-y", "-ss", "0",
        "-i", str(source), "-frames:v", "1", "-vf", "scale=320:-2", "-q:v", "3", str(destination),
    ]
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            shell=False,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise TimelineMediaError("FFmpeg could not create the clip thumbnail.") from exc
    if completed.returncode != 0 or not destination.is_file() or destination.stat().st_size == 0:
        raise TimelineMediaError("FFmpeg did not create a valid clip thumbnail.")


ProbeFunction = Callable[[Path, Path], ProbedMedia]
ThumbnailFunction = Callable[[Path, Path, Path], None]


class TimelineMediaStore:
    def __init__(
        self,
        data_dir: Path,
        *,
        ffprobe: Path | None,
        ffmpeg: Path | None,
        probe: ProbeFunction = probe_media,
        thumbnailer: ThumbnailFunction = create_thumbnail,
    ):
        self.data_dir = data_dir.resolve()
        self.ffprobe = ffprobe
        self.ffmpeg = ffmpeg
        self.probe = probe
        self.thumbnailer = thumbnailer

    @staticmethod
    def normalize_id(media_id: str | UUID) -> UUID:
        try:
            parsed = media_id if isinstance(media_id, UUID) else UUID(str(media_id))
        except (ValueError, TypeError, AttributeError) as exc:
            raise InvalidTimelineMediaId("Timeline media ID must be a valid UUID.") from exc
        if str(parsed) != str(media_id).lower():
            raise InvalidTimelineMediaId("Timeline media ID must use canonical UUID format.")
        return parsed

    def _directory(self, media_id: str | UUID) -> Path:
        parsed = self.normalize_id(media_id)
        directory = (self.data_dir / str(parsed)).resolve()
        if directory.parent != self.data_dir:
            raise InvalidTimelineMediaId("Timeline media path escaped its configured directory.")
        return directory

    @staticmethod
    def _safe_suffix(filename: str, kind: TimelineMediaKind) -> str:
        if not filename or any(character in filename for character in ("/", "\\", "\x00")):
            raise TimelineMediaError("Only a media filename without path components is accepted.")
        suffix = PurePosixPath(filename).suffix.lower()
        if suffix not in ALLOWED_SUFFIXES[kind]:
            if kind == TimelineMediaKind.CLIP:
                expected = "MP4"
            elif kind in IMAGE_KINDS:
                expected = "PNG, JPEG, or WebP"
            else:
                expected = "WAV, MP3, or M4A"
            raise TimelineMediaError(f"{kind.value.capitalize()} media must be {expected}.")
        return suffix

    @staticmethod
    def _validate_signature(path: Path, suffix: str) -> None:
        with path.open("rb") as handle:
            header = handle.read(16)
        if suffix in {".mp4", ".m4a"}:
            valid = len(header) >= 12 and header[4:8] == b"ftyp"
        elif suffix == ".png":
            valid = header.startswith(b"\x89PNG\r\n\x1a\n")
        elif suffix in {".jpg", ".jpeg"}:
            valid = header.startswith(b"\xff\xd8\xff")
        elif suffix == ".webp":
            valid = len(header) >= 12 and header[:4] == b"RIFF" and header[8:12] == b"WEBP"
        elif suffix == ".wav":
            valid = len(header) >= 12 and header[:4] == b"RIFF" and header[8:12] == b"WAVE"
        else:
            valid = header.startswith(b"ID3") or (
                len(header) >= 2 and header[0] == 0xFF and (header[1] & 0xE0) == 0xE0
            )
        if not valid:
            raise TimelineMediaError("Media signature does not match its filename extension.")

    @staticmethod
    def _atomic_bytes(path: Path, content: bytes) -> None:
        temporary: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(dir=path.parent, suffix=".tmp", delete=False) as handle:
                temporary = Path(handle.name)
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, path)
        finally:
            if temporary and temporary.exists():
                temporary.unlink()

    @staticmethod
    def _atomic_copy(source: Path, destination: Path) -> None:
        temporary: Path | None = None
        try:
            with source.open("rb") as incoming, tempfile.NamedTemporaryFile(
                dir=destination.parent, suffix=".tmp", delete=False
            ) as outgoing:
                temporary = Path(outgoing.name)
                shutil.copyfileobj(incoming, outgoing, length=1024 * 1024)
                outgoing.flush()
                os.fsync(outgoing.fileno())
            os.replace(temporary, destination)
        finally:
            if temporary and temporary.exists():
                temporary.unlink()

    def create_from_path(self, filename: str, source: Path, kind: TimelineMediaKind) -> TimelineMediaRecord:
        if not source.is_file():
            raise TimelineMediaError("Timeline source media was not found.")
        suffix = self._safe_suffix(filename, kind)
        size = source.stat().st_size
        if size <= 0 or size > MAX_MEDIA_BYTES[kind]:
            raise TimelineMediaError(f"{kind.value.capitalize()} media is empty or exceeds its size limit.")
        self._validate_signature(source, suffix)
        if not self.ffprobe:
            raise TimelineMediaError("FFprobe is required to validate timeline media.")
        probed = self.probe(source, self.ffprobe)
        if kind == TimelineMediaKind.CLIP and (
            probed.width is None or probed.height is None or probed.duration_seconds <= 0
        ):
            raise TimelineMediaError("Timeline clips must contain a decodable video stream.")
        if kind in {TimelineMediaKind.VOICE, TimelineMediaKind.MUSIC} and (
            not probed.has_audio or probed.duration_seconds <= 0
        ):
            raise TimelineMediaError("Timeline audio must contain a decodable audio stream.")
        if kind in IMAGE_KINDS and (probed.width is None or probed.height is None):
            raise TimelineMediaError("Timeline images must contain a decodable image stream.")

        media_id = uuid4()
        directory = self._directory(media_id)
        directory.mkdir(parents=True, exist_ok=False)
        stored_filename = f"source{suffix}"
        destination = directory / stored_filename
        try:
            self._atomic_copy(source, destination)
            thumbnail_filename = None
            if kind == TimelineMediaKind.CLIP or kind in IMAGE_KINDS:
                if not self.ffmpeg:
                    raise TimelineMediaError("FFmpeg is required to create timeline thumbnails.")
                thumbnail_filename = "thumbnail.jpg"
                self.thumbnailer(destination, directory / thumbnail_filename, self.ffmpeg)
            record = TimelineMediaRecord(
                media_id=media_id,
                kind=kind,
                created_at=utc_now(),
                original_filename=filename,
                stored_filename=stored_filename,
                content_type=CONTENT_TYPES[suffix],
                bytes=size,
                duration_seconds=probed.duration_seconds,
                width=probed.width,
                height=probed.height,
                frame_rate=probed.frame_rate,
                codec=probed.codec,
                has_audio=probed.has_audio,
                thumbnail_filename=thumbnail_filename,
            )
            self._atomic_bytes(directory / "metadata.json", record.model_dump_json(indent=2).encode("utf-8"))
            return record
        except Exception:
            if directory.parent == self.data_dir and directory.exists():
                shutil.rmtree(directory)
            raise

    def get(self, media_id: str | UUID) -> TimelineMediaRecord:
        metadata = self._directory(media_id) / "metadata.json"
        if not metadata.is_file():
            raise TimelineMediaNotFound("Timeline media was not found.")
        try:
            payload = json.loads(metadata.read_text(encoding="utf-8"))
            if payload.get("schema_version") != "1.0":
                raise CorruptTimelineMedia("Unsupported timeline media schema version.")
            record = TimelineMediaRecord.model_validate(payload)
        except CorruptTimelineMedia:
            raise
        except (OSError, json.JSONDecodeError, ValidationError, AttributeError) as exc:
            raise CorruptTimelineMedia("Timeline media metadata is corrupt.") from exc
        if record.media_id != self.normalize_id(media_id):
            raise CorruptTimelineMedia("Timeline media ID does not match its directory.")
        return record

    def media_path(self, media_id: str | UUID) -> tuple[Path, TimelineMediaRecord]:
        record = self.get(media_id)
        directory = self._directory(record.media_id)
        path = (directory / record.stored_filename).resolve()
        if path.parent != directory or not path.is_file() or path.stat().st_size != record.bytes:
            raise CorruptTimelineMedia("Stored timeline media is missing or has changed.")
        return path, record

    def thumbnail_path(self, media_id: str | UUID) -> Path:
        record = self.get(media_id)
        if record.kind != TimelineMediaKind.CLIP or not record.thumbnail_filename:
            raise TimelineMediaNotFound("Timeline thumbnail was not found.")
        directory = self._directory(record.media_id)
        path = (directory / record.thumbnail_filename).resolve()
        if path.parent != directory or not path.is_file():
            raise CorruptTimelineMedia("Timeline thumbnail is missing or unsafe.")
        return path
