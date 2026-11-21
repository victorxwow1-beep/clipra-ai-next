"""Free local full request -> worker -> editable clip -> playable export."""
from pathlib import Path

from clipra.db import Session
from clipra.models import Media
from clipra.worker import run_pending
from clipra.youtube_source import YouTubeImportError
from clipra.media import sha256_file

from .conftest import upload_file


def test_free_suggest_creates_editable_clips_and_renders_mp4(client, source):
    media = upload_file(client, source)
    request = client.post(
        f"/api/media/{media['id']}/suggest",
        json={"max_clips": 3, "length_seconds": 18},
    )
    assert request.status_code == 202, request.text
    job_id = request.json()["id"]
    duplicate = client.post(
        f"/api/media/{media['id']}/suggest",
        json={"max_clips": 3, "length_seconds": 18},
    )
    assert duplicate.json()["id"] == job_id
    assert run_pending(max_jobs=1) == 1
    status = client.get(f"/api/jobs/{job_id}").json()
    assert status["status"] == "done", status
    clips = client.get(f"/api/media/{media['id']}/clips").json()
    assert clips
    assert all(c["origin"] == "signal_draft" for c in clips)
    assert all(c["confidence"] is None for c in clips)
    assert all("review" in c["reasoning"].lower() for c in clips)
    render = client.post(f"/api/clips/{clips[0]['id']}/render")
    assert render.status_code == 202
    assert run_pending(max_jobs=1) == 1
    binary = client.get(f"/api/clips/{clips[0]['id']}/download")
    assert binary.status_code == 200
    assert len(binary.content) > 10000


def test_free_suggest_does_not_require_external_ai_consent(client, source):
    media = upload_file(client, source)
    result = client.post(
        f"/api/media/{media['id']}/suggest",
        json={"max_clips": 1, "length_seconds": 22},
    )
    assert result.status_code == 202


def test_youtube_import_requires_rights_and_valid_host(client):
    url = "https://youtube.com/watch?v=dQw4w9WgXcQ"
    assert client.post("/api/youtube/import", json={
        "url": url, "rights_confirmed": False
    }).status_code == 400
    assert client.post("/api/youtube/import", json={
        "url": "https://example.com/watch?v=dQw4w9WgXcQ",
        "rights_confirmed": True
    }).status_code == 422


def test_youtube_import_worker_persists_actual_media(client, source, monkeypatch):
    url = "https://www.youtube.com/live/dQw4w9WgXcQ"
    def safe_fixture_import(video_id, root):
        assert video_id == "dQw4w9WgXcQ"
        from clipra.media import verify_decodable
        metadata = verify_decodable(source)
        return {
            "path": source, "filename": "youtube-sample.mp4",
            "sha256": sha256_file(source),
            "size": source.stat().st_size,
            "youtube_url": f"https://www.youtube.com/watch?v={video_id}",
            "source_status": "video_or_replay",
            **{key: metadata[key] for key in (
                "duration", "width", "height", "fps", "has_audio"
            )},
        }
    monkeypatch.setattr("clipra.worker.download_authorized_youtube", safe_fixture_import)
    queued = client.post("/api/youtube/import", json={
        "url": url, "rights_confirmed": True
    })
    assert queued.status_code == 202, queued.text
    media_id = queued.json()["media_id"]
    assert media_id not in {m["id"] for m in client.get("/api/media").json()}
    run_pending(max_jobs=1)
    status = client.get(f"/api/jobs/{queued.json()['id']}").json()
    assert status["status"] == "done", status
    assert media_id in {m["id"] for m in client.get("/api/media").json()}
    imported = client.get(f"/api/media/{media_id}").json()
    assert imported["has_audio"] is True


def test_youtube_failure_never_creates_playable_placeholder(client, monkeypatch):
    def blocked(video_id, root):
        raise YouTubeImportError("Public YouTube media is inaccessible to this host")
    monkeypatch.setattr("clipra.worker.download_authorized_youtube", blocked)
    queued = client.post("/api/youtube/import", json={
        "url": "https://youtu.be/dQw4w9WgXcQ", "rights_confirmed": True
    })
    assert queued.status_code == 202
    run_pending(max_jobs=1)
    state = client.get(f"/api/jobs/{queued.json()['id']}").json()
    assert state["status"] == "blocked"
    assert queued.json()["media_id"] not in {m["id"] for m in client.get("/api/media").json()}


def test_website_exposes_free_mode_without_paid_gate():
    data = (Path(__file__).resolve().parents[1] /
            "clipra" / "site" / "app.js").read_text()
    assert "data-act=\"suggest\"" in data
    assert "data-act=\"importYoutube\"" in data
    assert "No AI credits" in data
