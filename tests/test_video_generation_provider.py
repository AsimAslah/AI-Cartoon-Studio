from types import SimpleNamespace

import pytest

from app.services.video_generation.contracts import VideoGenerationRequest, VideoProviderState
from app.services.video_generation.huggingface_provider import (
    HuggingFaceLTXProvider,
    HuggingFaceVideoConfig,
    VideoProviderAuthenticationError,
    VideoProviderNotConfiguredError,
    VideoProviderQuotaError,
    VideoProviderSchemaError,
    VideoProviderTimeoutError,
)


PARAMETERS = [
    "prompt", "image_path", "height", "width", "duration_s", "seed",
    "decoder", "auto_len", "randomize_seed", "do_enhance",
]


def request(upload_id):
    return VideoGenerationRequest(
        upload_id=upload_id,
        prompt="The white lion slowly checks his gold wristwatch.",
        remote_processing_consent=True,
    )


class FakeJob:
    def __init__(self, result, *, never_done=False):
        self._result = result
        self.never_done = never_done
        self.done_calls = 0
        self.cancelled = False
        self.communicator = SimpleNamespace(event_id="hf-event-123")

    def done(self):
        self.done_calls += 1
        return False if self.never_done else self.done_calls > 1

    def status(self):
        return SimpleNamespace(code=SimpleNamespace(value="IN_QUEUE"))

    def result(self, timeout=None):
        return self._result

    def cancel(self):
        self.cancelled = True


class FakeClient:
    def __init__(self, result, schema=None):
        self.result = result
        self.schema = schema or {
            "named_endpoints": {
                "/run": {"parameters": [{"parameter_name": name} for name in PARAMETERS]}
            }
        }
        self.submitted = None
        self.closed = False

    def view_api(self, return_format):
        assert return_format == "dict"
        return self.schema

    def submit(self, **kwargs):
        self.submitted = kwargs
        return FakeJob(self.result)

    def close(self):
        self.closed = True


def provider(client, **kwargs):
    return HuggingFaceLTXProvider(
        HuggingFaceVideoConfig(enabled=True, token="test-token", timeout_seconds=60, poll_interval_seconds=0),
        ffprobe_available=True,
        client_factory=lambda *args, **factory_kwargs: client,
        handle_file_factory=lambda path: {"uploaded": path},
        sleep=lambda _seconds: None,
        **kwargs,
    )


def test_gradio_provider_forwards_verified_ltx_schema_and_prompt(tmp_path):
    image = tmp_path / "reference.png"
    image.write_bytes(b"image")
    remote_output = tmp_path / "remote.mp4"
    remote_output.write_bytes(b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 1100)
    client = FakeClient((str(remote_output), "enhanced motion prompt", 42, "done"))
    adapter = provider(client)
    states = []
    result = adapter.generate(request(__import__("uuid").uuid4()), image, tmp_path / "job", lambda *value: states.append(value))
    assert client.submitted["api_name"] == "/run"
    assert client.submitted["prompt"].startswith("The white lion")
    assert client.submitted["image_path"] == {"uploaded": str(image)}
    assert client.submitted["duration_s"] == 3.0
    assert client.submitted["width"] == 1024
    assert result.provider_job_id == "hf-event-123"
    assert result.effective_prompt == "enhanced motion prompt"
    assert result.effective_seed == 42
    assert (tmp_path / "job" / "generated.mp4").is_file()
    assert ("PROVIDER_QUEUED", "hf-event-123") in states
    assert client.closed is True


def test_provider_rejects_changed_space_schema(tmp_path):
    client = FakeClient("unused", schema={"named_endpoints": {"/run": {"parameters": []}}})
    with pytest.raises(VideoProviderSchemaError, match="schema changed"):
        provider(client).generate(
            request(__import__("uuid").uuid4()), tmp_path / "image.png", tmp_path / "job", lambda *_: None
        )


def test_provider_maps_quota_and_authentication_errors(tmp_path):
    class TooManyRequestsError(Exception):
        pass

    class QuotaClient(FakeClient):
        def submit(self, **kwargs):
            raise TooManyRequestsError("429 quota")

    with pytest.raises(VideoProviderQuotaError):
        provider(QuotaClient("unused")).generate(
            request(__import__("uuid").uuid4()), tmp_path / "image.png", tmp_path / "job", lambda *_: None
        )

    def auth_factory(*args, **kwargs):
        raise RuntimeError("401 authentication token rejected")

    adapter = HuggingFaceLTXProvider(
        HuggingFaceVideoConfig(enabled=True, token="test-token"),
        ffprobe_available=True,
        client_factory=auth_factory,
        handle_file_factory=lambda path: path,
    )
    with pytest.raises(VideoProviderAuthenticationError):
        adapter.generate(request(__import__("uuid").uuid4()), tmp_path / "image.png", tmp_path / "job", lambda *_: None)


def test_provider_timeout_cancels_remote_job(tmp_path):
    class TimeoutClient(FakeClient):
        def __init__(self):
            super().__init__("unused")
            self.job = FakeJob("unused", never_done=True)

        def submit(self, **kwargs):
            return self.job

    client = TimeoutClient()
    clock_values = iter([0.0, 2.0])
    adapter = HuggingFaceLTXProvider(
        HuggingFaceVideoConfig(enabled=True, token="test-token", timeout_seconds=1, poll_interval_seconds=0),
        ffprobe_available=True,
        client_factory=lambda *args, **kwargs: client,
        handle_file_factory=lambda path: path,
        sleep=lambda _seconds: None,
        clock=lambda: next(clock_values),
    )
    with pytest.raises(VideoProviderTimeoutError):
        adapter.generate(request(__import__("uuid").uuid4()), tmp_path / "image.png", tmp_path / "job", lambda *_: None)
    assert client.job.cancelled is True


def test_disabled_provider_never_connects(tmp_path):
    adapter = HuggingFaceLTXProvider(
        HuggingFaceVideoConfig(enabled=False),
        ffprobe_available=True,
        client_factory=lambda *args, **kwargs: pytest.fail("client must not be constructed"),
        handle_file_factory=lambda path: path,
    )
    with pytest.raises(VideoProviderNotConfiguredError):
        adapter.generate(request(__import__("uuid").uuid4()), tmp_path / "image.png", tmp_path / "job", lambda *_: None)


def test_enabled_provider_requires_explicit_token_and_never_connects(tmp_path):
    adapter = HuggingFaceLTXProvider(
        HuggingFaceVideoConfig(enabled=True, token=None),
        ffprobe_available=True,
        client_factory=lambda *args, **kwargs: pytest.fail("client must not use a cached token"),
        handle_file_factory=lambda path: path,
    )
    capabilities = adapter.capabilities()
    assert capabilities.credentials_required is True
    assert capabilities.credentials_configured is False
    assert capabilities.state == VideoProviderState.AUTHENTICATION_REQUIRED
    assert capabilities.configured is False
    with pytest.raises(VideoProviderNotConfiguredError, match="AI_CARTOON_HF_TOKEN"):
        adapter.generate(request(__import__("uuid").uuid4()), tmp_path / "image.png", tmp_path / "job", lambda *_: None)


def test_invalid_timeout_environment_is_reported_as_configuration_error(monkeypatch):
    monkeypatch.setenv("AI_CARTOON_VIDEO_TIMEOUT_SECONDS", "not-a-number")
    with pytest.raises(VideoProviderNotConfiguredError, match="must be an integer"):
        HuggingFaceVideoConfig.from_env()
