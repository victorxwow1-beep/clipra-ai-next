"""Real Tesseract frame OCR: source evidence must beat generic motion.

No AI API mock is used by the positive/negative OCR tests; they render
actual synthetic moving-picture files and inspect genuine decoded pixels.
"""
import subprocess
from pathlib import Path

from clipra.semantic_evidence import (
    classify_hud_text, evidenced_moments, analyze_hud_video
)
from clipra.worker import run_pending
from .conftest import upload_file


def make_hud_video(tmp_path):
    src = tmp_path / "hud-evidence.mp4"
    overlay = (
        "drawtext=text='OtherPlayer eliminated Rival':fontsize=58:"
        "fontcolor=white:x=80:y=280:enable='between(t,0,2)',"
        "drawtext=text='You eliminated the opponent':fontsize=58:"
        "fontcolor=white:x=80:y=280:enable='between(t,3,6)'"
    )
    subprocess.run([
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-f", "lavfi", "-i", "color=c=black:s=1280x720:r=12:d=9",
        "-vf", overlay, "-c:v", "libx264", "-preset", "ultrafast", "-crf", "28",
        str(src)
    ], check=True, timeout=60)
    return src


def test_explicit_evidence_gate_rejects_others_and_idle():
    assert classify_hud_text("You eliminated the opponent")["kind"] == "player_elimination"
    assert classify_hud_text("Winner Winner Chicken Dinner")["kind"] == "match_win"
    assert classify_hud_text("OtherPlayer eliminated Rival") is None
    assert classify_hud_text("A teammate killed an opponent") is None
    assert evidenced_moments(90, [(10,"Loading"), (50, "OtherPlayer eliminated Rival")]) == []


def test_real_ocr_reads_actual_video_frames(tmp_path):
    source = make_hud_video(tmp_path)
    found, meta = analyze_hud_video(source, 9, [], max_clips=4,
                                   clip_length=18, max_frames=18)
    assert len(found) == 1, found
    assert found[0]["origin"] == "local_text_evidence"
    assert "You eliminated" in found[0]["reason"]
    assert "review" in found[0]["reason"].lower()
    assert meta["frames_checked"] > 0
    assert meta["coverage"] == "sampled_only_not_exhaustive"


def test_free_evidence_full_upload_worker_render_pipeline(client, tmp_path):
    source = make_hud_video(tmp_path)
    media = upload_file(client, source)
    url = f"/api/media/{media['id']}/evidence"
    queued = client.post(url, json={"max_clips": 3, "length_seconds": 18})
    assert queued.status_code == 202, queued.text
    duplicate = client.post(url, json={"max_clips": 3, "length_seconds": 18})
    assert duplicate.json()["id"] == queued.json()["id"]
    assert run_pending(max_jobs=1) == 1
    status = client.get(f"/api/jobs/{queued.json()['id']}").json()
    assert status["status"] == "done", status
    assert status["settings"]["candidate_count"] == 1
    clips = client.get(f"/api/media/{media['id']}/clips").json()
    assert len(clips) == 1
    assert clips[0]["origin"] == "local_text_evidence"
    assert clips[0]["confidence"] is None
    r = client.post(f"/api/clips/{clips[0]['id']}/render")
    assert r.status_code == 202
    assert run_pending(max_jobs=1) == 1
    final = client.get(f"/api/clips/{clips[0]['id']}/download")
    assert final.status_code == 200
    assert len(final.content) > 1000


def test_no_evidence_means_no_fabricated_clips(client, source):
    media = upload_file(client, source)
    r = client.post(f"/api/media/{media['id']}/evidence",
                    json={"max_clips": 12, "length_seconds": 22})
    assert r.status_code == 202
    assert run_pending(max_jobs=1) == 1
    j = client.get(f"/api/jobs/{r.json()['id']}").json()
    assert j["status"] == "done", j
    assert j["settings"]["candidate_count"] == 0
    assert client.get(f"/api/media/{media['id']}/clips").json() == []


def test_website_free_evidence_controls():
    website = (Path(__file__).resolve().parents[1] / "clipra" / "site" / "app.js").read_text()
    assert 'data-act="evidence"' in website
    assert "No paid AI credits" in website
