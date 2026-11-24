"""CPU-only tests; no AI model, cloud request, or video generated."""

from pathlib import Path
import sys

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from app.services.lipsync_http import router
from app.services.lipsync_store import LipSyncUploadStore


@pytest.fixture()
def client():
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


PNG = b"\x89PNG\r\n\x1a\n" + b"test image bytes"
WAV = b"RIFF" + b"\x00\x00\x00\x00" + b"WAVEfmt " + b"audio"
MP4 = b"\x00\x00\x00\x18ftypisom" + b"test video bytes"
MP3 = b"ID3" + b"mock sound"


def portrait():
    return {
        "data": {"mode": "portrait", "language": "ml", "character_id": "sheru_bhai"},
        "files": {"source": ("sheru.png", PNG, "image/png"), "audio": ("malayalam.wav", WAV, "audio/wav")},
    }


def test_capabilities_are_honest(client):
    r = client.get("/api/lipsync/capabilities")
    assert r.status_code == 200
    d = r.json()
    assert d["language"] == "ml"
    assert d["input_modes"] == ["portrait", "video"]
    assert d["provider"]["configured"] is False
    assert d["provider"]["performs_real_lipsync"] is False
    assert d["real_generation_enabled"] is False
    assert {provider["provider_id"] for provider in d["providers"]} == {
        "none", "latentsync_local", "musetalk_local", "external_gpu"
    }
    assert not any(provider["configured"] for provider in d["providers"])


def test_valid_portrait_returns_validation_not_generated_clip(client):
    r = client.post("/api/lipsync/validate", **portrait())
    assert r.status_code == 200
    assert r.json()["valid"] is True
    assert r.json()["mode"] == "portrait"
    assert r.json()["language"] == "ml"
    assert r.json()["decode_verified"] is False
    assert r.json()["lip_sync_performed"] is False


def test_valid_video_mode(client):
    r = client.post(
        "/api/lipsync/validate",
        data={"mode": "video"},
        files={"source": ("sheru.mp4", MP4, "video/mp4"), "audio": ("ml.mp3", MP3, "audio/mpeg")},
    )
    assert r.status_code == 200
    assert r.json()["source"]["kind"] == "video"


def test_wrong_extension_mode(client):
    p = portrait()
    p["files"]["source"] = ("sheru.mp4", MP4, "video/mp4")
    assert client.post("/api/lipsync/validate", **p).status_code == 422


def test_invalid_magic_bytes(client):
    p = portrait()
    p["files"]["audio"] = ("ml.wav", b"garbage", "audio/wav")
    r = client.post("/api/lipsync/validate", **p)
    assert r.status_code == 422
    assert "signature" in r.json()["detail"]


def test_english_not_substituted(client):
    p = portrait()
    p["data"]["language"] = "en"
    assert client.post("/api/lipsync/validate", **p).status_code == 422


def test_unsafe_filename(client):
    p = portrait()
    p["files"]["source"] = ("../sheru.png", PNG, "image/png")
    assert client.post("/api/lipsync/validate", **p).status_code == 422


def test_empty_audio(client):
    p = portrait()
    p["files"]["audio"] = ("ml.wav", b"", "audio/wav")
    assert client.post("/api/lipsync/validate", **p).status_code == 422


def test_size_limit(client, monkeypatch):
    from app.services.lipsync_contract import MAX_FILE_BYTES
    monkeypatch.setitem(MAX_FILE_BYTES, "audio", 5)
    r = client.post("/api/lipsync/validate", **portrait())
    assert r.status_code == 422
    assert "size limit" in r.json()["detail"]


def test_no_provider_never_generates_or_bills(client):
    r = client.post("/api/lipsync/jobs", **portrait())
    assert r.status_code == 503
    assert "No job was created" in r.json()["detail"]
    assert "no API was charged" in r.json()["detail"]


def test_prepared_upload_is_saved_and_previewed_locally(client, tmp_path, monkeypatch):
    import app.services.lipsync_http as http_module
    monkeypatch.setattr(http_module, "_upload_store", LipSyncUploadStore(tmp_path))
    created = client.post("/api/lipsync/uploads", **portrait())
    assert created.status_code == 201
    payload = created.json()
    assert payload["status"] == "VALIDATED"
    assert payload["request"]["language"] == "ml"
    assert payload["decode_verified"] is False

    loaded = client.get(f"/api/lipsync/uploads/{payload['upload_id']}")
    assert loaded.status_code == 200
    source = client.get(payload["source_preview_url"])
    audio = client.get(payload["audio_preview_url"])
    assert source.content == PNG
    assert audio.content == WAV
    assert source.headers["content-type"].startswith("image/png")
    assert source.headers["x-content-type-options"] == "nosniff"


def test_prepared_upload_job_reports_provider_unavailable(client, tmp_path, monkeypatch):
    import app.services.lipsync_http as http_module
    monkeypatch.setattr(http_module, "_upload_store", LipSyncUploadStore(tmp_path))
    upload_id = client.post("/api/lipsync/uploads", **portrait()).json()["upload_id"]
    response = client.post(
        "/api/lipsync/jobs", data={"upload_id": upload_id, "provider_id": "latentsync_local"}
    )
    assert response.status_code == 503
    assert "No job was created" in response.json()["detail"]
    assert "no API was charged" in response.json()["detail"]


def test_upload_preview_rejects_unsafe_id_and_unknown_job(client):
    assert client.get("/api/lipsync/uploads/not-a-uuid").status_code == 422
    assert client.get("/api/lipsync/jobs/not-a-uuid").status_code == 404


def test_no_source_file_returns_422(client):
    p = portrait()
    del p["files"]["source"]
    assert client.post("/api/lipsync/validate", **p).status_code == 422


def test_external_clients_are_rejected():
    app = FastAPI()
    app.include_router(router)
    with TestClient(app, client=("192.0.2.40", 1234)) as c:
        assert c.post("/api/lipsync/validate", **portrait()).status_code == 403


def test_installer_preserves_other_routes_and_is_idempotent(tmp_path, monkeypatch):
    from scripts.install_lipsync_api_step3 import install
    root = tmp_path
    (root / "app" / "services").mkdir(parents=True)
    (root / "app" / "services" / "lipsync_contract.py").touch()
    (root / "app" / "services" / "lipsync_http.py").touch()
    main = root / "app" / "main.py"
    main.write_text(
        'from fastapi import FastAPI\n'
        'app = FastAPI(title="Demo")\n'
        'app.mount("/static", object(), name="static")\n'
        '@app.get("/alive")\n'
        'def alive(): return "yes"\n', encoding="utf-8"
    )
    assert "Registered" in install(root)
    installed = main.read_text(encoding="utf-8")
    assert "def alive(): return" in installed
    assert installed.count("app.include_router(lipsync_router)") == 1
    assert "Already installed" in install(root)
    assert installed == main.read_text(encoding="utf-8")


def test_installer_does_not_edit_unfamiliar_main(tmp_path):
    from scripts.install_lipsync_api_step3 import install
    (tmp_path / "app" / "services").mkdir(parents=True)
    (tmp_path / "app" / "services" / "lipsync_contract.py").touch()
    (tmp_path / "app" / "services" / "lipsync_http.py").touch()
    main = tmp_path / "app" / "main.py"
    main.write_text("print('hello')\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="refusing to edit"):
        install(tmp_path)
    assert main.read_text(encoding="utf-8") == "print('hello')\n"
