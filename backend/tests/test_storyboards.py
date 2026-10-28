import io

import pytest

from backend.core.security import validate_relative_path
from backend.media import ffmpeg

from PIL import Image


def _png_bytes(width: int = 64, height: int = 32, color=(10, 200, 90)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (width, height), color=color).save(buf, format="PNG")
    return buf.getvalue()


def _upload(client, name: str, data: bytes) -> dict:
    response = client.post("/api/assets/upload", files={"file": (name, data, "image/png")})
    assert response.status_code == 200, response.text
    return response.json()


@pytest.fixture()
def storyboard(client):
    created = client.post(
        "/api/storyboards",
        json={"title": "Animatic Uji", "aspect": "16:9", "fps": 24},
    )
    assert created.status_code == 200, created.text
    return created.json()


def test_probe_reports_real_metadata(tmp_path):
    work = tmp_path / "work"
    out = tmp_path / "out" / "probe.mp4"
    img = tmp_path / "img.png"
    img.write_bytes(_png_bytes(320, 180))
    meta = ffmpeg.render_animatic(
        [img], [0.6], out, work, size=(640, 360), fps=24
    )
    assert meta["codec"] == "h264"
    assert meta["width"] == 640 and meta["height"] == 360
    assert abs(meta["duration"] - 0.6) < 0.5


def test_storyboard_crud_and_validation(client, storyboard):
    sb_id = storyboard["id"]
    fetched = client.get(f"/api/storyboards/{sb_id}").json()
    assert fetched["title"] == "Animatic Uji"
    assert fetched["status"] == "draft"

    bad_aspect = client.post("/api/storyboards", json={"title": "x", "aspect": "21:9"})
    assert bad_aspect.status_code == 422

    updated = client.patch(f"/api/storyboards/{sb_id}", json={"title": "Animatic Uji 2", "fps": 12})
    assert updated.status_code == 200
    assert updated.json()["fps"] == 12

    deleted = client.delete(f"/api/storyboards/{sb_id}")
    assert deleted.status_code == 200
    assert client.get(f"/api/storyboards/{sb_id}").status_code == 404


def test_scene_rules_and_reorder(client, storyboard):
    sb_id = storyboard["id"]
    asset_a = _upload(client, "a.png", _png_bytes(color=(200, 10, 10)))
    asset_b = _upload(client, "b.png", _png_bytes(32, 64, color=(10, 10, 200)))

    added_a = client.post(
        f"/api/storyboards/{sb_id}/scenes",
        json={"asset_id": asset_a["id"], "duration_sec": 0.5, "note": "opening"},
    )
    assert added_a.status_code == 200, added_a.text
    added_b = client.post(
        f"/api/storyboards/{sb_id}/scenes",
        json={"asset_id": asset_b["id"], "duration_sec": 0.5},
    )
    assert added_b.status_code == 200

    bad_duration = client.post(
        f"/api/storyboards/{sb_id}/scenes",
        json={"asset_id": asset_a["id"], "duration_sec": 99},
    )
    assert bad_duration.status_code in {400, 422}

    missing_asset = client.post(
        f"/api/storyboards/{sb_id}/scenes",
        json={"asset_id": "ast_missing", "duration_sec": 1},
    )
    assert missing_asset.status_code == 400

    scene_b_id = added_b.json()["scenes"][1]["id"]
    moved = client.patch(f"/api/storyboards/{sb_id}/scenes/{scene_b_id}", json={"idx": 0})
    assert moved.status_code == 200, moved.text
    assert moved.json()["scenes"][0]["asset"]["id"] == asset_b["id"]

    removed = client.delete(f"/api/storyboards/{sb_id}/scenes/{scene_b_id}")
    assert removed.status_code == 200
    assert len(removed.json()["scenes"]) == 1
    assert removed.json()["scenes"][0]["idx"] == 0


def test_render_empty_storyboard_rejected(client, storyboard):
    response = client.post(f"/api/storyboards/{storyboard['id']}/render")
    assert response.status_code == 400
    assert "kosong" in response.json()["detail"]


def test_render_animatic_produces_real_mp4(client, storyboard):
    sb_id = storyboard["id"]
    asset_a = _upload(client, "scene-a.png", _png_bytes(320, 180, color=(200, 60, 10)))
    asset_b = _upload(client, "scene-b.png", _png_bytes(320, 180, color=(10, 60, 200)))
    client.post(f"/api/storyboards/{sb_id}/scenes", json={"asset_id": asset_a["id"], "duration_sec": 0.5})
    client.post(f"/api/storyboards/{sb_id}/scenes", json={"asset_id": asset_b["id"], "duration_sec": 0.5})

    rendered = client.post(f"/api/storyboards/{sb_id}/render")
    assert rendered.status_code == 200, rendered.text
    body = rendered.json()
    assert body["status"] == "rendered"
    assert body["output_asset_id"]

    asset = client.get(f"/api/assets/{body['output_asset_id']}").json()
    assert asset["file_type"] == "video"
    assert asset["mime_type"] == "video/mp4"
    assert asset["source"] == "render"

    video = client.get(f"/api/assets/{body['output_asset_id']}/file")
    assert video.status_code == 200
    assert video.content[:12] == b"\x00\x00\x00 ftypisom"

    meta = ffmpeg.probe(validate_relative_path(asset["path"]))
    assert meta["codec"] == "h264"
    assert abs((meta["duration"] or 0) - 1.0) < 0.6


def test_render_video_asset_as_keyframe_rejected(client, storyboard):
    # asset video tidak boleh jadi keyframe: buat asset video via upload mp4 sintetis
    mp4 = b"\x00\x00\x00 ftypisom" + b"A" * 2048
    upload = client.post(
        "/api/assets/upload",
        files={"file": ("fake.mp4", mp4, "video/mp4")},
    )
    assert upload.status_code == 200
    response = client.post(
        f"/api/storyboards/{storyboard['id']}/scenes",
        json={"asset_id": upload.json()["id"], "duration_sec": 1},
    )
    assert response.status_code == 400
    assert "gambar" in response.json()["detail"]


def _wav_bytes(seconds: float = 1.0, rate: int = 8000) -> bytes:
    import wave

    buf = io.BytesIO()
    with wave.open(buf, "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(rate)
        handle.writeframes(b"\x00\x00" * int(rate * seconds))
    return buf.getvalue()


def test_audio_upload_and_crossfade_render(client, storyboard):
    sb_id = storyboard["id"]
    audio = client.post(
        "/api/assets/upload",
        files={"file": ("bed.wav", _wav_bytes(2.0), "audio/wav")},
    )
    assert audio.status_code == 200, audio.text
    audio_body = audio.json()
    assert audio_body["file_type"] == "audio"
    assert audio_body["mime_type"] == "audio/wav"

    image_a = _upload(client, "fade-a.png", _png_bytes(color=(210, 40, 40)))
    image_b = _upload(client, "fade-b.png", _png_bytes(color=(40, 40, 210)))
    client.post(f"/api/storyboards/{sb_id}/scenes", json={"asset_id": image_a["id"], "duration_sec": 1.0})
    client.post(f"/api/storyboards/{sb_id}/scenes", json={"asset_id": image_b["id"], "duration_sec": 1.0})

    patched = client.patch(
        f"/api/storyboards/{sb_id}",
        json={"transition": "fade", "transition_sec": 0.3, "audio_asset_id": audio_body["id"]},
    )
    assert patched.status_code == 200, patched.text
    body = patched.json()
    assert body["transition"] == "fade"
    assert body["transition_sec"] == 0.3
    assert body["audio_asset"]["filename"] == "bed.wav"
    assert abs(body["duration_total"] - 1.7) < 0.001

    rendered = client.post(f"/api/storyboards/{sb_id}/render")
    assert rendered.status_code == 200, rendered.text
    asset = client.get(f"/api/assets/{rendered.json()['output_asset_id']}").json()
    meta = ffmpeg.probe(validate_relative_path(asset["path"]))
    assert meta["has_audio"] is True
    assert meta["audio_codec"] == "aac"
    assert meta["codec"] == "h264"
    assert abs((meta["duration"] or 0) - 1.7) < 0.5


def test_audio_track_must_be_audio_asset(client, storyboard):
    sb_id = storyboard["id"]
    image = _upload(client, "not-audio.png", _png_bytes())
    response = client.patch(f"/api/storyboards/{sb_id}", json={"audio_asset_id": image["id"]})
    assert response.status_code == 400
    assert "audio" in response.json()["detail"].lower()


def test_invalid_transition_rejected(client, storyboard):
    response = client.patch(f"/api/storyboards/{storyboard['id']}", json={"transition": "warp"})
    assert response.status_code == 400
    assert "transisi" in response.json()["detail"].lower()


def test_transition_longer_than_scene_rejected(client, storyboard):
    sb_id = storyboard["id"]
    image = _upload(client, "short.png", _png_bytes())
    client.post(f"/api/storyboards/{sb_id}/scenes", json={"asset_id": image["id"], "duration_sec": 0.5})
    client.post(f"/api/storyboards/{sb_id}/scenes", json={"asset_id": image["id"], "duration_sec": 0.5})
    patched = client.patch(f"/api/storyboards/{sb_id}", json={"transition": "fade", "transition_sec": 1.0})
    assert patched.status_code == 200, patched.text
    rendered = client.post(f"/api/storyboards/{sb_id}/render")
    assert rendered.status_code == 400
    assert "transisi" in rendered.json()["detail"].lower()
