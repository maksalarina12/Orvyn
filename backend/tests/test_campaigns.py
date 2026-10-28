import io
import zipfile

import pytest

from backend.core.security import validate_relative_path

from PIL import Image


def _png_bytes(width: int = 320, height: int = 180, color=(90, 120, 200)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (width, height), color=color).save(buf, format="PNG")
    return buf.getvalue()


def _upload(client, name: str, data: bytes) -> dict:
    response = client.post("/api/assets/upload", files={"file": (name, data, "image/png")})
    assert response.status_code == 200, response.text
    return response.json()


@pytest.fixture()
def campaign(client):
    created = client.post("/api/campaigns", json={"name": "Launch Kopi", "description": "teaser + banner"})
    assert created.status_code == 200, created.text
    return created.json()


def test_campaign_crud_and_status(client, campaign):
    cmp_id = campaign["id"]
    fetched = client.get(f"/api/campaigns/{cmp_id}").json()
    assert fetched["name"] == "Launch Kopi"
    assert fetched["status"] == "draft"
    assert fetched["assets"] == []

    updated = client.patch(f"/api/campaigns/{cmp_id}", json={"status": "active"})
    assert updated.status_code == 200
    assert updated.json()["status"] == "active"

    bad_status = client.patch(f"/api/campaigns/{cmp_id}", json={"status": "viral"})
    assert bad_status.status_code == 400

    deleted = client.delete(f"/api/campaigns/{cmp_id}")
    assert deleted.status_code == 200
    assert client.get(f"/api/campaigns/{cmp_id}").status_code == 404


def test_campaign_assets_bundle_rules(client, campaign):
    cmp_id = campaign["id"]
    asset_a = _upload(client, "banner.png", _png_bytes())
    asset_b = _upload(client, "hero.png", _png_bytes(color=(200, 120, 10)))

    added = client.post(f"/api/campaigns/{cmp_id}/assets", json={"asset_id": asset_a["id"], "role": "banner"})
    assert added.status_code == 200, added.text
    client.post(f"/api/campaigns/{cmp_id}/assets", json={"asset_id": asset_b["id"], "role": "hero"})

    missing = client.post(f"/api/campaigns/{cmp_id}/assets", json={"asset_id": "ast_missing"})
    assert missing.status_code == 400

    bundle = client.get(f"/api/campaigns/{cmp_id}").json()
    assert [a["role"] for a in bundle["assets"]] == ["banner", "hero"]

    removed = client.delete(f"/api/campaigns/{cmp_id}/assets/{asset_b['id']}")
    assert removed.status_code == 200
    assert len(removed.json()["assets"]) == 1


def test_overlay_creates_new_asset_linked_to_campaign(client, campaign):
    cmp_id = campaign["id"]
    asset = _upload(client, "photo.png", _png_bytes(640, 360, color=(20, 20, 30)))
    client.post(f"/api/campaigns/{cmp_id}/assets", json={"asset_id": asset["id"], "role": "base"})

    overlay = client.post(
        f"/api/campaigns/{cmp_id}/overlay",
        json={"asset_id": asset["id"], "text": "Kopi Pagi Hari", "position": "bottom", "font_size": 64, "color": "#ffd166"},
    )
    assert overlay.status_code == 200, overlay.text
    body = overlay.json()
    new_asset = body["asset"]
    assert new_asset["source"] == "overlay"
    assert new_asset["revision_of"] == asset["id"]
    assert new_asset["width"] == 640 and new_asset["height"] == 360

    rendered = Image.open(validate_relative_path(new_asset["path"]))
    assert rendered.size == (640, 360)
    # band bawah berubah dari warna polos sumber
    pixel = rendered.convert("RGB").getpixel((320, 355))
    assert pixel != (20, 20, 30)

    assets_in_campaign = body["campaign"]["assets"]
    assert any(a["id"] == new_asset["id"] and a["role"] == "overlay" for a in assets_in_campaign)

    not_in_campaign = client.post(
        f"/api/campaigns/{cmp_id}/overlay",
        json={"asset_id": _upload(client, "outsider.png", _png_bytes())["id"], "text": "x"},
    )
    assert not_in_campaign.status_code == 400
    assert "campaign ini" in not_in_campaign.json()["detail"]


def test_overlay_validation(client, campaign):
    asset = _upload(client, "v.png", _png_bytes())
    client.post(f"/api/campaigns/{campaign['id']}/assets", json={"asset_id": asset["id"]})
    bad = client.post(
        f"/api/campaigns/{campaign['id']}/overlay",
        json={"asset_id": asset["id"], "text": "x", "position": "left"},
    )
    assert bad.status_code == 422
    empty = client.post(
        f"/api/campaigns/{campaign['id']}/overlay",
        json={"asset_id": asset["id"], "text": "   "},
    )
    assert empty.status_code == 422


def test_export_creates_zip_with_manifest(client, campaign):
    cmp_id = campaign["id"]
    asset = _upload(client, "asset-export.png", _png_bytes(color=(10, 200, 120)))
    client.post(f"/api/campaigns/{cmp_id}/assets", json={"asset_id": asset["id"], "role": "hero"})

    empty = client.post(
        "/api/campaigns",
        json={"name": "Kosong"},
    ).json()
    empty_export = client.post(f"/api/campaigns/{empty['id']}/export")
    assert empty_export.status_code == 400

    exported = client.post(f"/api/campaigns/{cmp_id}/export")
    assert exported.status_code == 200, exported.text
    info = exported.json()
    assert info["asset_count"] == 1
    assert info["file_size"] > 0

    downloaded = client.get(f"/api/campaigns/{cmp_id}/export/download")
    assert downloaded.status_code == 200
    assert downloaded.headers["content-type"] == "application/zip"

    bundle = zipfile.ZipFile(io.BytesIO(downloaded.content))
    names = bundle.namelist()
    assert "manifest.json" in names
    assert "asset-export.png" in names
    manifest = __import__("json").loads(bundle.read("manifest.json"))
    assert manifest["campaign"]["id"] == cmp_id
    assert manifest["asset_count"] == 1
    assert manifest["assets"][0]["sha256"]
    assert manifest["assets"][0]["role"] == "hero"
