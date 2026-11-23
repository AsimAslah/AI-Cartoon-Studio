from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

import app.services.video_generation.http as http_module
from app.services.video_generation.huggingface_provider import VideoProviderNotConfiguredError
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
