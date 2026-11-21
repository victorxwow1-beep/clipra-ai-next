"""CLIPRA v5: actual upload → smart OCR → render → ZIP → reject.

Speech selection unit tests use human-known transcript segments. Actual Whisper
weights remain an independent runtime verification requirement.
"""
import io
import json
from pathlib import Path
from zipfile import ZipFile

from clipra.local_speech import speech_moments
from clipra.worker import run_pending
from .conftest import upload_file
from .test_local_semantic_webflow import make_hud_video


def test_voice_selection_keeps_real_words_not_fake_events():
    raw=[
        {"start":2,"end":7,"text":"The first reason to use the system is that it preserves the source video."},
        {"start":7.2,"end":12,"text":"For example a complete answer should keep context and end naturally."},
        {"start":12.1,"end":16,"text":"We can show the entire reasoning clearly in the final segment."},
        {"start":70,"end":71,"text":"Um."}
    ]
    found=speech_moments(120,raw,max_clips=5,clip_length=24,category="education")
    assert 1 <= len(found) <= 5
    assert all(x["origin"]=="local_speech" for x in found)
    assert all("actual locally transcribed speech" in x["reason"].lower() for x in found)
    assert all(x["start"]>=0 and x["end"]<=120 for x in found)
    assert speech_moments(120,[{"start":0,"end":2,"text":"Um."}],max_clips=5)==[]


def test_real_hud_smart_to_independent_zip_and_reject(client,tmp_path):
    original=make_hud_video(tmp_path)
    media=upload_file(client,original)
    payload={"category":"gaming","max_clips":3,"length_seconds":24,
             "ratio":"original","mode":"fit","crf":20}
    run=client.post(f"/api/media/{media['id']}/smart",json=payload)
    assert run.status_code==202,run.text
    duplicate=client.post(f"/api/media/{media['id']}/smart",json=payload)
    assert duplicate.json()["id"]==run.json()["id"]
    assert run_pending(max_jobs=1)==1
    completed=client.get("/api/jobs/"+run.json()["id"]).json()
    assert completed["status"]=="done",completed
    assert completed["settings"]["candidate_count"]==1
    found=client.get(f"/api/media/{media['id']}/clips").json()
    assert len(found)==1 and found[0]["origin"]=="local_text_evidence"
    forbidden=client.get(f"/api/media/{media['id']}/download-all")
    assert forbidden.status_code==409
    clip=found[0]
    render=client.post("/api/clips/"+clip["id"]+"/render")
    assert render.status_code==202
    assert run_pending(max_jobs=1)==1
    audio=client.get("/api/clips/"+clip["id"]+"/download")
    assert audio.status_code==200 and audio.content[:4]!=b""
    archive=client.get(f"/api/media/{media['id']}/download-all")
    assert archive.status_code==200,archive.text[:400] if archive.status_code!=200 else ""
    with ZipFile(io.BytesIO(archive.content)) as z:
        names=z.namelist()
        assert len(names)==1 and names[0].endswith(".mp4")
        assert z.read(names[0])==audio.content
    assert client.delete("/api/clips/"+clip["id"]).status_code==204
    assert client.get(f"/api/media/{media['id']}/clips").json()==[]
    assert client.get("/api/clips/"+clip["id"]+"/download").status_code==404
    assert original.exists()


def test_local_funny_model_rejected_without_fabrication(client,source):
    m=upload_file(client,source)
    response=client.post(f"/api/media/{m['id']}/smart",
        json={"category":"funny","max_clips":5,"length_seconds":24})
    assert response.status_code==503
    assert "open-source vision" in response.json()["detail"]


def test_free_speech_mode_is_routed_and_no_credit_key_needed(client,source,monkeypatch):
    m=upload_file(client,source)
    evidence={"model":"faster-whisper/tiny","language":"en","scope":"actual transcript"}
    def mock_transcript(path,duration,*,max_clips,clip_length,category):
        assert category=="podcast"
        return ([{"start":1.0,"end":14.5,"title":"Spoken moment",
            "reason":"Actual locally transcribed speech: The talk is complete. Review context.",
            "origin":"local_speech"}],evidence)
    monkeypatch.setattr("clipra.worker.transcribe_local",mock_transcript)
    run=client.post(f"/api/media/{m['id']}/smart",
                    json={"category":"podcast","max_clips":3,"length_seconds":24,
                          "ratio":"original"})
    assert run.status_code==202,run.text
    assert run_pending(max_jobs=1)==1
    assert client.get("/api/jobs/"+run.json()["id"]).json()["status"]=="done"
    clips=client.get(f"/api/media/{m['id']}/clips").json()
    assert len(clips)==1
    assert clips[0]["origin"]=="local_speech"
    assert clips[0]["confidence"] is None


def test_website_is_easy_mobile_first(client):
    home=client.get("/")
    assert home.status_code==200
    assert "/studio-assets/app-v5.js" in home.text
    js=client.get("/studio-assets/app-v5.js")
    css=client.get("/studio-assets/style-v5.css")
    assert js.status_code==200 and css.status_code==200
    for phrase in ("Find Best Clips","How many clips?","Length per clip",
                   "Video type","Gallery / Files","YouTube Link",
                   "Download All ZIP","Reject","customMinutes","customSeconds"):
        assert phrase in js.text
    assert "max-width:650px" in css.text
    assert "Higgsfield credits" in js.text
