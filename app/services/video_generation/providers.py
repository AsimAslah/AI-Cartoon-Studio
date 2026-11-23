from __future__ import annotations

import os
from pathlib import Path

from app.services.video_generation.huggingface_provider import (
    HuggingFaceLTXProvider,
    HuggingFaceVideoConfig,
    VideoProviderError,
)
from app.services.video_generation.media_validation import discover_ffprobe


def build_huggingface_provider() -> tuple[HuggingFaceLTXProvider, Path | None]:
    configured_probe = os.environ.get("AI_CARTOON_FFPROBE_PATH") or None
    ffprobe = discover_ffprobe(configured_probe)
    try:
        config = HuggingFaceVideoConfig.from_env()
        error = None
    except VideoProviderError as exc:
        config = HuggingFaceVideoConfig(enabled=False)
        error = str(exc)
    return HuggingFaceLTXProvider(config, ffprobe_available=ffprobe is not None, configuration_error=error), ffprobe
