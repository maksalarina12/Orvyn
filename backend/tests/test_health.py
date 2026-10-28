def test_health_reports_honest_state(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] in {"ok", "degraded", "error"}
    assert data["checks"]["storage"]["ok"] is True
    assert data["checks"]["database"]["ok"] is True
    assert data["checks"]["ffmpeg"]["ok"] is True
    inference = data["checks"]["inference_backend"]
    assert inference["ok"] is False
    assert inference["types"]


def test_root_and_config(client):
    assert client.get("/").json()["status"] == "running"
    cfg = client.get("/api/config").json()
    assert cfg["max_upload_mb"] > 0
