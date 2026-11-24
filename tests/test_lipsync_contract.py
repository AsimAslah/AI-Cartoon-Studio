"""CPU-only, offline tests for the future Malayalam lip-sync feature."""

import pytest
from pydantic import ValidationError

from app.services.lipsync_contract import (
    InputMode,
    LipSyncRequest,
    MediaValidationError,
    ProviderUnavailableError,
    UnconfiguredLipSyncProvider,
    validate_media_bytes,
)


def test_request_accepts_malayalam_portrait_and_video():
    portrait = LipSyncRequest(mode="portrait", source_filename="Sheru.png", audio_filename="dialogue.wav")
    video = LipSyncRequest(mode="video", source_filename="scene.mp4", audio_filename="dialogue.mp3")
    assert portrait.language == video.language == "ml"
    assert portrait.mode == InputMode.PORTRAIT
    assert video.mode == InputMode.VIDEO


def test_request_rejects_incorrect_media_mode():
    with pytest.raises(ValidationError):
        LipSyncRequest(mode="portrait", source_filename="scene.mp4", audio_filename="dialogue.wav")
    with pytest.raises(ValidationError):
        LipSyncRequest(mode="video", source_filename="hero.jpg", audio_filename="dialogue.wav")


def test_request_disallows_path_traversal_and_language_substitution():
    with pytest.raises(ValidationError):
        LipSyncRequest(mode="portrait", source_filename="../hero.png", audio_filename="dialogue.wav")
    with pytest.raises(ValidationError):
        LipSyncRequest(mode="portrait", source_filename="hero.png", audio_filename="dialogue.wav", language="en")


def test_media_signatures_pass():
    validate_media_bytes("image", "hero.png", b"\x89PNG\r\n\x1a\n" + b"test")
    validate_media_bytes("audio", "voice.wav", b"RIFF" + b"\x00" * 4 + b"WAVEfmt ")
    validate_media_bytes("video", "clip.mp4", b"\x00\x00\x00\x18ftypisom")


@pytest.mark.parametrize("kind,name,content", [
    ("image", "hero.png", b"not-a-png"),
    ("audio", "voice.wav", b"not-wav"),
    ("video", "clip.mp4", b"not-mp4"),
    ("image", "../hero.png", b"\x89PNG\r\n\x1a\n"),
    ("audio", "voice.mp3", b""),
])
def test_invalid_media_rejected(kind, name, content):
    with pytest.raises(MediaValidationError):
        validate_media_bytes(kind, name, content)


def test_unconfigured_backend_never_pretends_to_generate():
    adapter = UnconfiguredLipSyncProvider()
    assert adapter.capabilities().configured is False
    assert adapter.capabilities().performs_real_lipsync is False
    with pytest.raises(ProviderUnavailableError, match="No video was generated"):
        adapter.submit(
            LipSyncRequest(mode="portrait", source_filename="lion.png", audio_filename="ml.wav"),
            b"image", b"audio"
        )
