from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path, PurePosixPath

from app.services.video_generation.contracts import VideoMetadata

MAX_IMAGE_BYTES = 20 * 1024 * 1024
ALLOWED_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}
IMAGE_CONTENT_TYPES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
}


class VideoMediaValidationError(ValueError):
    pass


class VideoOutputVerificationError(RuntimeError):
    pass


def safe_image_suffix(filename: str) -> str:
    if not filename or not filename.strip():
        raise VideoMediaValidationError("Image filename is required.")
    if any(character in filename for character in ("/", "\\", "\x00")) or filename in {".", ".."}:
        raise VideoMediaValidationError("Only an image filename without path components is accepted.")
    suffix = PurePosixPath(filename).suffix.lower()
    if suffix not in ALLOWED_IMAGE_EXTENSIONS:
        raise VideoMediaValidationError("Reference image must be PNG, JPEG, or WebP.")
    return suffix


def validate_image_bytes(filename: str, content: bytes) -> str:
    suffix = safe_image_suffix(filename)
    if not content:
        raise VideoMediaValidationError("Reference image is empty.")
    if len(content) > MAX_IMAGE_BYTES:
        raise VideoMediaValidationError("Reference image exceeds the 20 MB limit.")
    if suffix == ".png":
        valid = content.startswith(b"\x89PNG\r\n\x1a\n")
    elif suffix in {".jpg", ".jpeg"}:
        valid = content.startswith(b"\xff\xd8\xff")
    else:
        valid = len(content) >= 12 and content[:4] == b"RIFF" and content[8:12] == b"WEBP"
    if not valid:
        raise VideoMediaValidationError("Image content signature does not match its extension.")
    return suffix


def discover_ffprobe(configured_path: str | None = None) -> Path | None:
    if configured_path:
        candidate = Path(configured_path).expanduser()
        return candidate.resolve() if candidate.is_file() else None
    found = shutil.which("ffprobe")
    return Path(found).resolve() if found else None


def _rate(value: str) -> float:
    numerator, separator, denominator = value.partition("/")
    if separator:
        divisor = float(denominator)
        return float(numerator) / divisor if divisor else 0.0
    return float(value)


def probe_mp4(path: Path, ffprobe: Path, *, timeout_seconds: int = 30) -> VideoMetadata:
    if not path.is_file() or path.stat().st_size < 1_024:
        raise VideoOutputVerificationError("Generated MP4 is missing or too small.")
    command = [
        str(ffprobe),
        "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=codec_name,width,height,avg_frame_rate,duration:format=duration",
        "-of", "json",
        str(path),
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
        raise VideoOutputVerificationError("ffprobe could not inspect the generated MP4.") from exc
    if completed.returncode != 0:
        detail = (completed.stderr or "ffprobe rejected the generated MP4.")[-1_000:]
        raise VideoOutputVerificationError(detail)
    try:
        payload = json.loads(completed.stdout)
        stream = payload["streams"][0]
        duration = float(stream.get("duration") or payload["format"]["duration"])
        metadata = VideoMetadata(
            width=int(stream["width"]),
            height=int(stream["height"]),
            duration_seconds=duration,
            frame_rate=_rate(stream["avg_frame_rate"]),
            codec=str(stream["codec_name"]),
        )
    except (KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise VideoOutputVerificationError("ffprobe returned incomplete video metadata.") from exc
    return metadata
