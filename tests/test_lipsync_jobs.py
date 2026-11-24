from pathlib import Path

import pytest

from app.services.lipsync_contract import (
    InputMode,
    LipSyncJobRequest,
    LipSyncJobState,
    LipSyncRequest,
    ProviderAvailability,
    ProviderCapabilities,
    ProviderUnavailableError,
)
from app.services.lipsync_jobs import LipSyncJobManager
from app.services.lipsync_store import LipSyncUploadStore


PNG = b"\x89PNG\r\n\x1a\nportrait"
WAV = b"RIFF" + b"\x00" * 4 + b"WAVEfmt audio"


class FakeRealProvider:
    def __init__(self, fail=False):
        self.fail = fail

    def capabilities(self):
        return ProviderCapabilities(
            provider_id="verified_test",
            name="Verified test provider",
            configured=True,
            modes=[InputMode.PORTRAIT, InputMode.VIDEO],
            performs_real_lipsync=True,
            availability=ProviderAvailability.AVAILABLE,
            note="Injected only in tests.",
        )

    def generate(self, upload, source_path: Path, audio_path: Path, output_dir: Path) -> Path:
        assert source_path.read_bytes() == PNG
        assert audio_path.read_bytes() == WAV
        if self.fail:
            raise RuntimeError("Provider failed truthfully")
        output = output_dir / "result.mp4"
        output.write_bytes(b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 1100)
        return output


def prepared_upload(tmp_path):
    store = LipSyncUploadStore(tmp_path / "uploads")
    record = store.create(
        LipSyncRequest(mode="portrait", source_filename="sheru.png", audio_filename="dialogue.wav"),
        PNG,
        WAV,
    )
    source, _ = store.media_path(record.upload_id, "source")
    audio, _ = store.media_path(record.upload_id, "audio")
    return record, source, audio


def test_real_provider_contract_has_truthful_states_and_verified_output(tmp_path):
    upload, source, audio = prepared_upload(tmp_path)
    manager = LipSyncJobManager(tmp_path / "jobs", {"verified_test": FakeRealProvider()})
    queued = manager.submit(
        LipSyncJobRequest(upload_id=upload.upload_id, provider_id="verified_test"), upload, source, audio
    )
    completed = manager.wait(queued.job_id)
    assert completed.state == LipSyncJobState.COMPLETED
    assert completed.state_history == [
        LipSyncJobState.QUEUED,
        LipSyncJobState.PREPARING,
        LipSyncJobState.SUBMITTING,
        LipSyncJobState.PROCESSING,
        LipSyncJobState.VERIFYING,
        LipSyncJobState.COMPLETED,
    ]
    assert manager.output_path(queued.job_id).name == "result.mp4"
    manager.shutdown()


def test_provider_failure_is_captured_without_false_completion(tmp_path):
    upload, source, audio = prepared_upload(tmp_path)
    manager = LipSyncJobManager(tmp_path / "jobs", {"verified_test": FakeRealProvider(fail=True)})
    queued = manager.submit(
        LipSyncJobRequest(upload_id=upload.upload_id, provider_id="verified_test"), upload, source, audio
    )
    failed = manager.wait(queued.job_id)
    assert failed.state == LipSyncJobState.FAILED
    assert "failed truthfully" in failed.error
    assert LipSyncJobState.COMPLETED not in failed.state_history
    manager.shutdown()


def test_unavailable_provider_never_creates_a_job(tmp_path):
    upload, source, audio = prepared_upload(tmp_path)
    manager = LipSyncJobManager(tmp_path / "jobs")
    with pytest.raises(ProviderUnavailableError, match="No job was created"):
        manager.submit(LipSyncJobRequest(upload_id=upload.upload_id, provider_id="none"), upload, source, audio)
    assert manager._jobs == {}
    manager.shutdown()
