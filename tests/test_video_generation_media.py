import json
from types import SimpleNamespace

import pytest

from app.services.video_generation.media_validation import (
    VideoMediaValidationError,
    VideoOutputVerificationError,
    probe_mp4,
    validate_image_bytes,
)
from app.services.video_generation.store import (
    CorruptVideoUploadError,
    InvalidVideoUploadIdError,
    VideoInputStore,
)


PNG = b"\x89PNG\r\n\x1a\nreference"
JPEG = b"\xff\xd8\xffreference"
WEBP = b"RIFF" + b"\x00" * 4 + b"WEBPreference"


@pytest.mark.parametrize(("name", "content"), [("hero.png", PNG), ("hero.jpg", JPEG), ("hero.webp", WEBP)])
def test_valid_reference_formats(name, content):
    assert validate_image_bytes(name, content) == "." + name.rsplit(".", 1)[1]


@pytest.mark.parametrize(
    ("name", "content"),
    [("../hero.png", PNG), ("hero.gif", b"GIF89a"), ("hero.png", b"wrong"), ("hero.png", b"")],
)
def test_invalid_reference_images_are_rejected(name, content):
    with pytest.raises(VideoMediaValidationError):
        validate_image_bytes(name, content)


def test_video_input_store_preserves_bytes_and_rejects_path_ids(tmp_path):
    store = VideoInputStore(tmp_path)
    record = store.create("sheru.webp", WEBP)
    loaded = store.get(record.upload_id)
    path, media_type = store.image_path(record.upload_id)
    assert loaded == record
    assert path.read_bytes() == WEBP
    assert media_type == "image/webp"
    assert not list(tmp_path.rglob("*.tmp"))
    with pytest.raises(InvalidVideoUploadIdError):
        store.get("../outside")


def test_video_input_store_detects_changed_media(tmp_path):
    store = VideoInputStore(tmp_path)
    record = store.create("sheru.png", PNG)
    path, _ = store.image_path(record.upload_id)
    path.write_bytes(b"changed")
    with pytest.raises(CorruptVideoUploadError, match="changed"):
        store.image_path(record.upload_id)


def test_ffprobe_metadata_is_parsed_without_shell(monkeypatch, tmp_path):
    video = tmp_path / "generated.mp4"
    video.write_bytes(b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 1100)
    payload = {
        "streams": [{"codec_name": "h264", "width": 1024, "height": 576, "avg_frame_rate": "24/1", "duration": "3.5"}],
        "format": {"duration": "3.5"},
    }

    def fake_run(command, **kwargs):
        assert kwargs["shell"] is False
        assert command[-1] == str(video)
        return SimpleNamespace(returncode=0, stdout=json.dumps(payload), stderr="")

    monkeypatch.setattr("app.services.video_generation.media_validation.subprocess.run", fake_run)
    metadata = probe_mp4(video, tmp_path / "ffprobe.exe")
    assert metadata.width == 1024
    assert metadata.height == 576
    assert metadata.frame_rate == 24
    assert metadata.duration_seconds == 3.5


def test_ffprobe_failure_rejects_output(monkeypatch, tmp_path):
    video = tmp_path / "generated.mp4"
    video.write_bytes(b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 1100)
    monkeypatch.setattr(
        "app.services.video_generation.media_validation.subprocess.run",
        lambda *args, **kwargs: SimpleNamespace(returncode=1, stdout="", stderr="corrupt stream"),
    )
    with pytest.raises(VideoOutputVerificationError, match="corrupt stream"):
        probe_mp4(video, tmp_path / "ffprobe.exe")
