import io
import json
import zipfile

from backend.database.db import db_session
from backend.jobs import service as job_service


def test_bulk_zip_returns_archive(client, png_bytes):
    ids = []
    for name in ("satu.png", "dua.png"):
        uploaded = client.post("/api/assets/upload", files={"file": (name, png_bytes, "image/png")})
        assert uploaded.status_code == 200, uploaded.text
        ids.append(uploaded.json()["id"])

    response = client.post("/api/assets/bulk-zip", json={"asset_ids": ids})
    assert response.status_code == 200, response.text
    assert response.headers["content-type"] == "application/zip"
    assert "attachment" in response.headers["content-disposition"]
    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        assert sorted(archive.namelist()) == ["dua.png", "satu.png"]
        assert archive.read("satu.png") == png_bytes


def test_bulk_zip_rejects_empty_and_missing(client):
    empty = client.post("/api/assets/bulk-zip", json={"asset_ids": []})
    assert empty.status_code == 422
    missing = client.post("/api/assets/bulk-zip", json={"asset_ids": ["ast_tidak_ada"]})
    assert missing.status_code == 404


def test_job_events_stream_terminal_job(client):
    with db_session() as conn:
        job = job_service.create_job(conn, "hf_space", "text_to_image", "uji sse", None, {"steps": 4})
        conn.execute(
            "UPDATE generation_jobs SET status = 'completed', finished_at = created_at, result_asset_ids = ? WHERE id = ?",
            (json.dumps([]), job["id"]),
        )
        conn.commit()

    response = client.get(f"/api/generations/{job['id']}/events")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert "event: job" in response.text
    data = json.loads(response.text.split("data: ", 1)[1].split("\n", 1)[0])
    assert data["status"] == "completed"


def test_job_events_missing_job(client):
    response = client.get("/api/generations/job_tidak_ada/events")
    assert response.status_code == 404
