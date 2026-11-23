from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient

import app.main as main_module
from app.main import app
from app.models import RenderJobResponse, RenderState
from app.services.project_store import ProjectStore

client = TestClient(app)


def test_health_capabilities_shape():
    response = client.get("/api/capabilities")
    assert response.status_code == 200
    assert response.json()["characters"] == ["fox"]


def test_storyboard_validation():
    response = client.post("/api/storyboard", json={"text": "   "})
    assert response.status_code == 422


def storyboard_payload(action="walk"):
    return {
        "schema_version": "1.0",
        "title": "API fox",
        "scenes": [
            {
                "scene_id": 1,
                "order": 0,
                "description": "The fox walks.",
                "environment": "magical_forest",
                "characters": ["fox"],
                "action": action,
                "narration": "The fox walks.",
                "duration_seconds": 2,
            }
        ],
    }


def test_storyboard_validation_endpoint_and_unsupported_action():
    response = client.post("/api/storyboard/validate", json=storyboard_payload())
    assert response.status_code == 200
    assert response.json()["valid"] is True

    response = client.post("/api/storyboard/validate", json=storyboard_payload("fly"))
    assert response.status_code == 422
    assert "idle" in response.text and "touch" in response.text


def test_project_crud_endpoints(tmp_path, monkeypatch):
    monkeypatch.setattr(main_module, "project_store", ProjectStore(tmp_path))
    payload = {"name": "Saved fox", "story_text": "A fox walks.", "storyboard": storyboard_payload()}
    created = client.post("/api/projects", json=payload)
    assert created.status_code == 201
    project_id = created.json()["project_id"]

    listed = client.get("/api/projects")
    assert listed.status_code == 200
    assert listed.json()["projects"][0]["project_id"] == project_id

    loaded = client.get(f"/api/projects/{project_id}")
    assert loaded.status_code == 200
    payload["name"] = "Updated fox"
    updated = client.put(f"/api/projects/{project_id}", json=payload)
    assert updated.status_code == 200
    assert updated.json()["name"] == "Updated fox"

    assert client.get("/api/projects/../secrets").status_code in {404, 422}
    assert client.get("/api/projects/not-a-uuid").status_code == 422


def test_render_submission_and_status_api(monkeypatch):
    job = RenderJobResponse(
        job_id=uuid4(),
        state=RenderState.QUEUED,
        message="Queued",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        scene_count=1,
    )

    class FakeManager:
        def submit(self, storyboard):
            return job

        def get(self, job_id):
            return job

    monkeypatch.setattr(main_module, "render_job_manager", FakeManager())
    monkeypatch.setattr(main_module, "discover_blender", lambda: Path("blender.exe"))
    response = client.post("/api/renders", json={"storyboard": storyboard_payload()})
    assert response.status_code == 202
    assert response.json()["state"] == "QUEUED"
    status_response = client.get(f"/api/renders/{job.job_id}")
    assert status_response.status_code == 200
