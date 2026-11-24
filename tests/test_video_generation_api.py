from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

import app.services.video_generation.http as http_module
from app.services.video_generation.contracts import VideoQuotaState, VideoQuotaStatus
from app.services.video_generation.huggingface_provider import (
    VideoProviderNotConfiguredError,
    VideoProviderUnknownError,
)
from app.services.video_generation.http import router
from app.services.video_generation.store import VideoInputStore


PNG = b"\x89PNG\r\n\x1a\nreference image"


@pytest.fixture()
def client():
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_video_capabilities_are_honest_and_provider_specific(client):
    response = client.get("/api/video/capabilities")
    assert response.status_code == 200
    provider = response.json()["provider"]
    assert provider["provider_id"] == "huggingface_ltx_2_5"
    assert provider["model_id"] == "Lightricks/LTX-2.5-Diffusers"
    assert provider["api_name"] == "/run"
    assert provider["supports_negative_prompt"] is False
    assert provider["supports_audio_toggle"] is False
    preset = response.json()["low_resource_preset"]
    assert preset["settings"] == {
        "duration_seconds": 1.0,
        "width": 1024,
        "height": 576,
        "seed": 42,
        "decoder": "conv",
        "auto_length": False,
        "randomize_seed": False,
        "enhance_prompt": False,
    }
    assert preset["attempt_limit"] == 1
    assert preset["expected_reservation_gpu_seconds"] == 120.0


def test_image_upload_and_safe_preview(client, tmp_path, monkeypatch):
    monkeypatch.setattr(http_module, "_store", VideoInputStore(tmp_path))
    created = client.post("/api/video/uploads", files={"image": ("sheru.png", PNG, "image/png")})
    assert created.status_code == 201
    payload = created.json()
    assert payload["original_filename"] == "sheru.png"
    preview = client.get(payload["preview_url"])
    assert preview.status_code == 200
    assert preview.content == PNG
    assert preview.headers["x-content-type-options"] == "nosniff"


@pytest.mark.parametrize(
    ("name", "content"),
    [("sheru.gif", b"GIF89a"), ("../sheru.png", PNG), ("sheru.png", b"not png"), ("sheru.png", b"")],
)
def test_invalid_image_uploads_return_422(client, tmp_path, monkeypatch, name, content):
    monkeypatch.setattr(http_module, "_store", VideoInputStore(tmp_path))
    assert client.post("/api/video/uploads", files={"image": (name, content, "application/octet-stream")}).status_code == 422


def job_payload(upload_id):
    return {
        "upload_id": upload_id,
        "provider_id": "huggingface_ltx_2_5",
        "prompt": "A white lion slowly checks his wristwatch inside a moving luxury car.",
        "remote_processing_consent": True,
        "settings": {"duration_seconds": 3, "width": 1024, "height": 576},
    }


def test_unconfigured_provider_returns_503_without_job(client, tmp_path, monkeypatch):
    store = VideoInputStore(tmp_path)
    monkeypatch.setattr(http_module, "_store", store)
    upload = client.post("/api/video/uploads", files={"image": ("sheru.png", PNG, "image/png")}).json()

    class UnavailableJobs:
        def submit(self, request, path):
            raise VideoProviderNotConfiguredError("Remote provider disabled; no quota consumed.")

    monkeypatch.setattr(http_module, "_jobs", UnavailableJobs())
    response = client.post("/api/video/jobs", json=job_payload(upload["upload_id"]))
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "provider_not_configured"
    assert "no quota consumed" in response.json()["detail"]["message"]


def test_empty_prompt_and_missing_consent_are_rejected(client):
    payload = job_payload("00000000-0000-0000-0000-000000000000")
    payload["prompt"] = "   "
    assert client.post("/api/video/jobs", json=payload).status_code == 422
    payload = job_payload("00000000-0000-0000-0000-000000000000")
    payload["remote_processing_consent"] = False
    assert client.post("/api/video/jobs", json=payload).status_code == 422


def test_unsafe_upload_id_unknown_job_and_external_clients(client):
    assert client.get("/api/video/uploads/not-a-uuid").status_code == 422
    assert client.get("/api/video/jobs/not-a-uuid").status_code == 404
    app = FastAPI()
    app.include_router(router)
    with TestClient(app, client=("192.0.2.50", 1234)) as external:
        assert external.get("/api/video/capabilities").status_code == 200
        assert external.post("/api/video/uploads", files={"image": ("sheru.png", PNG)}).status_code == 403
        assert external.get("/api/video/quota").status_code == 403
        assert external.post("/api/video/quota/refresh").status_code == 403


class StubQuota:
    def __init__(self, status):
        self.status = status
        self.refresh_calls = 0

    def current(self):
        return self.status

    def refresh(self):
        self.refresh_calls += 1
        return self.status


def quota_status(remaining=143.53):
    return VideoQuotaStatus(
        state=VideoQuotaState.AVAILABLE,
        authentication_status="authenticated",
        total_gpu_seconds=300,
        remaining_gpu_seconds=remaining,
        message="Quota available; acceptance is not guaranteed.",
    )


def test_quota_status_and_explicit_refresh_never_submit_inference(client, monkeypatch):
    quota = StubQuota(quota_status())
    monkeypatch.setattr(http_module, "_quota", quota)

    class JobsMustNotRun:
        def submit(self, request, path):
            pytest.fail("quota status must never submit inference")

    monkeypatch.setattr(http_module, "_jobs", JobsMustNotRun())
    current = client.get("/api/video/quota")
    refreshed = client.post("/api/video/quota/refresh")
    assert current.status_code == 200
    assert refreshed.status_code == 200
    assert refreshed.json()["remaining_gpu_seconds"] == 143.53
    assert quota.refresh_calls == 1


def test_known_insufficient_reservation_rejects_before_job_creation(client, tmp_path, monkeypatch):
    store = VideoInputStore(tmp_path)
    monkeypatch.setattr(http_module, "_store", store)
    monkeypatch.setattr(http_module, "_quota", StubQuota(quota_status(119.0)))
    upload = client.post("/api/video/uploads", files={"image": ("sheru.png", PNG, "image/png")}).json()

    class JobsMustNotRun:
        def submit(self, request, path):
            pytest.fail("known insufficient quota must reject before submission")

    monkeypatch.setattr(http_module, "_jobs", JobsMustNotRun())
    payload = job_payload(upload["upload_id"])
    payload["settings"].update({
        "duration_seconds": 1,
        "decoder": "conv",
        "seed": 42,
        "randomize_seed": False,
        "enhance_prompt": False,
        "auto_length": False,
    })
    response = client.post("/api/video/jobs", json=payload)
    assert response.status_code == 503
    detail = response.json()["detail"]
    assert detail["code"] == "zero_gpu_reservation_exceeds_remaining"
    assert detail["diagnostic_code"] == "hf_zero_gpu_reservation_exceeds_remaining"


def test_pre_submit_provider_error_response_is_sanitized(client, tmp_path, monkeypatch):
    store = VideoInputStore(tmp_path)
    monkeypatch.setattr(http_module, "_store", store)
    monkeypatch.setattr(http_module, "_quota", StubQuota(quota_status(300.0)))
    upload = client.post("/api/video/uploads", files={"image": ("sheru.png", PNG, "image/png")}).json()

    class FailedJobs:
        def submit(self, request, path):
            raise VideoProviderUnknownError(
                "Generation failed. The provider did not return enough information to identify the exact cause."
            )

    monkeypatch.setattr(http_module, "_jobs", FailedJobs())
    response = client.post("/api/video/jobs", json=job_payload(upload["upload_id"]))
    detail = response.json()["detail"]
    assert response.status_code == 503
    assert detail["code"] == "provider_failure_unknown"
    assert detail["diagnostic_code"] == "hf_unclassified_failure"
    assert "Authorization" not in detail["message"]
