def _create_project(client, name="Test Project", **overrides):
    payload = {"name": name, "description": "desc", "category": "general", "tags": ["tag1", "tag2"]}
    payload.update(overrides)
    response = client.post("/api/projects", json=payload)
    assert response.status_code == 200, response.text
    return response.json()


def test_project_crud_roundtrip(client):
    created = _create_project(client, name="My Campaign")
    project_id = created["id"]
    assert created["name"] == "My Campaign"
    assert created["tags"] == ["tag1", "tag2"]
    assert created["asset_count"] == 0

    fetched = client.get(f"/api/projects/{project_id}")
    assert fetched.status_code == 200
    assert fetched.json()["id"] == project_id

    updated = client.patch(f"/api/projects/{project_id}", json={"name": "Renamed", "category": "social_media"})
    assert updated.status_code == 200
    assert updated.json()["name"] == "Renamed"
    assert updated.json()["category"] == "social_media"

    listing = client.get("/api/projects", params={"query": "Renamed"})
    assert listing.status_code == 200
    assert any(item["id"] == project_id for item in listing.json()["items"])

    deleted = client.delete(f"/api/projects/{project_id}")
    assert deleted.status_code == 400

    deleted = client.delete(f"/api/projects/{project_id}", params={"confirm": "true"})
    assert deleted.status_code == 200
    assert client.get(f"/api/projects/{project_id}").status_code == 404


def test_project_validation(client):
    response = client.post("/api/projects", json={"name": "   "})
    assert response.status_code == 422
    response = client.post("/api/projects", json={"name": "x", "category": "nonsense"})
    assert response.status_code == 422
    response = client.post("/api/projects", json={"name": "x"})
    assert response.status_code == 200


def test_project_delete_keeps_assets(client, png_bytes):
    project = _create_project(client, name="Assets Here")
    upload = client.post(
        "/api/assets/upload",
        files={"file": ("test.png", png_bytes, "image/png")},
        data={"project_id": project["id"]},
    )
    assert upload.status_code == 200
    asset = upload.json()
    assert client.delete(f"/api/projects/{project['id']}", params={"confirm": "true"}).status_code == 200
    reopening = client.get(f"/api/assets/{asset['id']}")
    assert reopening.status_code == 200
    assert reopening.json()["project_id"] is None
