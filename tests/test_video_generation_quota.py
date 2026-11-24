from datetime import datetime, timezone
from types import SimpleNamespace

from app.services.video_generation.contracts import VideoQuotaState
from app.services.video_generation.quota import HuggingFaceQuotaService


NOW = datetime(2026, 11, 24, 18, 0, tzinfo=timezone.utc)
RESET = datetime(2026, 11, 24, 20, 37, tzinfo=timezone.utc)


class FakeApi:
    def __init__(self, result=None, error=None):
        self.result = result
        self.error = error
        self.tokens = []

    def get_zero_gpu_quota(self, *, token):
        self.tokens.append(token)
        if self.error:
            raise self.error
        return self.result


class QuotaHttpError(Exception):
    def __init__(self, status_code):
        super().__init__("upstream response must stay private")
        self.response = SimpleNamespace(status_code=status_code)


def test_quota_available_uses_explicit_token_and_formats_reset_timestamp():
    api = FakeApi(SimpleNamespace(base=300.0, remaining=143.53, resets_at=RESET))
    service = HuggingFaceQuotaService("test-token", api_factory=lambda token: api, clock=lambda: NOW)
    status = service.refresh()
    assert api.tokens == ["test-token"]
    assert status.state == VideoQuotaState.AVAILABLE
    assert status.authentication_status == "authenticated"
    assert status.total_gpu_seconds == 300.0
    assert status.remaining_gpu_seconds == 143.53
    assert status.last_successful_refresh_at == NOW
    payload = status.model_dump(mode="json")
    assert payload["resets_at"] == "2026-11-24T20:37:00Z"
    assert payload["last_successful_refresh_at"] == "2026-11-24T18:00:00Z"


def test_zero_quota_is_reported_as_exhausted():
    api = FakeApi(SimpleNamespace(base=300.0, remaining=0.0, resets_at=RESET))
    status = HuggingFaceQuotaService("test-token", api_factory=lambda token: api, clock=lambda: NOW).refresh()
    assert status.state == VideoQuotaState.EXHAUSTED
    assert "exhausted" in status.message


def test_missing_token_never_calls_quota_api():
    called = False

    def factory(_token):
        nonlocal called
        called = True
        return FakeApi()

    service = HuggingFaceQuotaService(None, api_factory=factory)
    status = service.refresh()
    assert called is False
    assert status.state == VideoQuotaState.AUTHENTICATION_REQUIRED
    assert status.authentication_status == "missing"


def test_quota_permission_failure_is_specific_and_sanitized():
    api = FakeApi(error=QuotaHttpError(403))
    status = HuggingFaceQuotaService("test-token", api_factory=lambda token: api).refresh()
    assert status.state == VideoQuotaState.PERMISSION_DENIED
    assert status.authentication_status == "permission_denied"
    assert "Billing > Read" in status.message
    assert "upstream response" not in status.message


def test_quota_authentication_failure_is_specific():
    api = FakeApi(error=QuotaHttpError(401))
    status = HuggingFaceQuotaService("test-token", api_factory=lambda token: api).refresh()
    assert status.state == VideoQuotaState.AUTHENTICATION_REQUIRED
    assert status.authentication_status == "invalid"


def test_failed_refresh_preserves_last_successful_refresh_time():
    api = FakeApi(SimpleNamespace(base=300.0, remaining=143.53, resets_at=RESET))
    service = HuggingFaceQuotaService("test-token", api_factory=lambda token: api, clock=lambda: NOW)
    service.refresh()
    api.error = RuntimeError("network details")
    failed = service.refresh()
    assert failed.state == VideoQuotaState.UNAVAILABLE
    assert failed.last_successful_refresh_at == NOW
    assert "network details" not in failed.message
