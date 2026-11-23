from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_capabilities_shape():
    response = client.get("/api/capabilities")
    assert response.status_code == 200
    assert response.json()["characters"] == ["fox"]


def test_storyboard_validation():
    response = client.post("/api/storyboard", json={"text": "   "})
    assert response.status_code == 422
