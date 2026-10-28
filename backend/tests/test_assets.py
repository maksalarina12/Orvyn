def test_upload_png_and_metadata(client, png_bytes):
    response = client.post(
        "/api/assets/upload",
        files={"file": (" test image.png ", png_bytes, "image/png")},
    )
    assert response.status_code == 200, response.text
    asset = response.json()
    assert asset["file_type"] == "image"
    assert asset["mime_type"] == "image/png"
    assert asset["width"] == 64
    assert asset["height"] == 32
    assert asset["file_size"] == len(png_bytes)
    assert asset["filename"] == "testimage.png"

    file_response = client.get(f"/api/assets/{asset['id']}/file")
    assert file_response.status_code == 200
    assert file_response.content == png_bytes

    updated = client.patch(f"/api/assets/{asset['id']}", json={"is_favorite": True, "notes": "hero shot"})
    assert updated.status_code == 200
    assert updated.json()["is_favorite"] is True

    deleted = client.delete(f"/api/assets/{asset['id']}", params={"confirm": "true", "delete_file": "true"})
    assert deleted.status_code == 200
    assert client.get(f"/api/assets/{asset['id']}").status_code == 404


def test_upload_rejects_unknown_type(client):
    response = client.post(
        "/api/assets/upload",
        files={"file": ("evil.sh", b"#!/bin/sh\nrm -rf /\n", "application/x-sh")},
    )
    assert response.status_code == 415


def test_upload_rejects_too_large(client, png_bytes):
    big = b"\x89PNG\r\n\x1a\n" + b"A" * (52 * 1024 * 1024)
    response = client.post(
        "/api/assets/upload",
        files={"file": ("big.png", big, "image/png")},
    )
    assert response.status_code == 413


def test_upload_project_must_exist(client, png_bytes):
    response = client.post(
        "/api/assets/upload",
        files={"file": ("x.png", png_bytes, "image/png")},
        data={"project_id": "prj_missing"},
    )
    assert response.status_code == 400


def test_asset_list_filters(client, png_bytes):
    upload = client.post(
        "/api/assets/upload",
        files={"file": ("filter-me.png", png_bytes, "image/png")},
    )
    asset = upload.json()
    favorites = client.get("/api/assets", params={"favorite_only": "true"})
    assert favorites.status_code == 200
    text = client.get("/api/assets", params={"query": "filter"})
    assert any(item["id"] == asset["id"] for item in text.json()["items"])


def test_asset_move_between_projects(client, png_bytes):
    project = client.post(
        "/api/projects",
        json={"name": "Move Target", "category": "general"},
    ).json()
    upload = client.post(
        "/api/assets/upload",
        files={"file": ("movable.png", png_bytes, "image/png")},
    )
    asset_id = upload.json()["id"]

    moved = client.patch(f"/api/assets/{asset_id}", json={"project_id": project["id"]})
    assert moved.status_code == 200, moved.text
    assert moved.json()["project_id"] == project["id"]

    in_project = client.get("/api/assets", params={"project_id": project["id"]})
    assert any(item["id"] == asset_id for item in in_project.json()["items"])

    unassigned = client.patch(f"/api/assets/{asset_id}", json={"project_id": ""})
    assert unassigned.status_code == 200
    assert unassigned.json()["project_id"] is None

    missing = client.patch(f"/api/assets/{asset_id}", json={"project_id": "prj_missing"})
    assert missing.status_code == 400
