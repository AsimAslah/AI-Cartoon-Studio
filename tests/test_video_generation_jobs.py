from uuid import uuid4

import pytest

from app.services.video_generation.contracts import (
    VideoGenerationRequest,
    VideoJobState,
    VideoMetadata,
    VideoProviderCapabilities,
    VideoProviderResult,
    VideoProviderState,
)
from app.services.video_generation.huggingface_provider import (
    VideoProviderNotConfiguredError,
    VideoProviderQuotaError,
)
from app.services.video_generation.jobs import VideoGenerationJobManager


class FakeProvider:
    provider_id = "huggingface_ltx_2_5"

    def __init__(self, error=None):
        self.error = error

    def capabilities(self):
        return VideoProviderCapabilities(
            provider_id=self.provider_id,
            name="Fake LTX provider",
            model_id="Lightricks/LTX-2.5-Diffusers",
            state=VideoProviderState.AVAILABLE,
            configured=True,
            credentials_required=False,
            credentials_configured=False,
            supported_image_types=["image/png"],
            supported_durations=[3.0],
            resolution_presets={"landscape": (1024, 576)},
            supported_decoders=["diffusion"],
            supports_seed=True,
            supports_prompt_enhancement=True,
            note="Test provider only.",
        )

    def generate(self, request, image_path, output_dir, state_callback):
        state_callback("SUBMITTED", "provider-event-1")
        state_callback("PROVIDER_QUEUED", "provider-event-1")
        state_callback("RUNNING", "provider-event-1")
        if self.error:
            raise self.error
        output = output_dir / "generated.mp4"
        output.write_bytes(b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 1100)
        state_callback("DOWNLOADING", "provider-event-1")
        return VideoProviderResult(
            provider_job_id="provider-event-1",
            output_path=str(output),
            effective_prompt=request.prompt,
            effective_seed=123,
        )


def generation_request():
    return VideoGenerationRequest(
        upload_id=uuid4(),
        prompt="A regal white lion checks his wristwatch inside a moving car.",
        remote_processing_consent=True,
    )


def metadata_probe(_path):
    return VideoMetadata(width=1024, height=576, duration_seconds=3.0, frame_rate=24.0, codec="h264")


def test_job_lifecycle_completes_only_after_mp4_metadata_verification(tmp_path):
    image = tmp_path / "reference.png"
    image.write_bytes(b"image")
    provider = FakeProvider()
    manager = VideoGenerationJobManager(tmp_path / "jobs", {provider.provider_id: provider}, metadata_probe)
    queued = manager.submit(generation_request(), image)
    completed = manager.wait(queued.job_id)
    assert completed.state == VideoJobState.COMPLETED
    assert completed.provider_job_id == "provider-event-1"
    assert completed.metadata.width == 1024
    assert completed.effective_seed == 123
    assert completed.state_history == [
        VideoJobState.QUEUED,
        VideoJobState.VALIDATING,
        VideoJobState.UPLOADING,
        VideoJobState.SUBMITTED,
        VideoJobState.PROVIDER_QUEUED,
        VideoJobState.RUNNING,
        VideoJobState.DOWNLOADING,
        VideoJobState.VERIFYING,
        VideoJobState.COMPLETED,
    ]
    assert manager.output_path(queued.job_id).name == "generated.mp4"
    manager.shutdown()


def test_quota_failure_is_captured_without_false_completion(tmp_path):
    image = tmp_path / "reference.png"
    image.write_bytes(b"image")
    provider = FakeProvider(VideoProviderQuotaError("quota exhausted"))
    manager = VideoGenerationJobManager(tmp_path / "jobs", {provider.provider_id: provider}, metadata_probe)
    queued = manager.submit(generation_request(), image)
    failed = manager.wait(queued.job_id)
    assert failed.state == VideoJobState.FAILED
    assert failed.error_code == "quota_exceeded"
    assert "quota exhausted" in failed.error
    assert VideoJobState.COMPLETED not in failed.state_history
    manager.shutdown()


def test_missing_provider_and_probe_reject_before_job_creation(tmp_path):
    image = tmp_path / "reference.png"
    image.write_bytes(b"image")
    request = generation_request()
    empty = VideoGenerationJobManager(tmp_path / "empty", {}, metadata_probe)
    with pytest.raises(VideoProviderNotConfiguredError):
        empty.submit(request, image)
    empty.shutdown()

    provider = FakeProvider()
    no_probe = VideoGenerationJobManager(tmp_path / "no-probe", {provider.provider_id: provider}, None)
    with pytest.raises(VideoProviderNotConfiguredError, match="ffprobe"):
        no_probe.submit(request, image)
    no_probe.shutdown()
