"""Real JPEG source-frame preview from a playable original, not mock imagery."""
from pathlib import Path
from fastapi.testclient import TestClient

from clipra.main import app
from .conftest import upload_file


def test_actual_jpeg_thumbnail_before_render_with_original_preserved(client,source):
    m=upload_file(client,source)
    create=client.post(f"/api/media/{m['id']}/clips",
        json={"title":"Context review","segments":[{"start":5,"end":12}],
              "ratio":"9:16","mode":"fit","crf":20})
    assert create.status_code==201,create.text
    clip=create.json()
    assert clip["rendered"] is False
    url=f"/api/clips/{clip['id']}/thumbnail"
    thumb=client.get(url)
    assert thumb.status_code==200,thumb.text[:200] if thumb.status_code!=200 else ""
    assert thumb.headers["content-type"].startswith("image/jpeg")
    assert thumb.content[:3]==b"\xff\xd8\xff"
    assert len(thumb.content)>800
    assert client.get(url).content==thumb.content
    edit=client.put(f"/api/clips/{clip['id']}",
        json={"title":"Edited context","segments":[{"start":9,"end":16}],
              "ratio":"9:16","mode":"fit","crf":20})
    assert edit.status_code==200
    after=client.get(url)
    assert after.status_code==200 and after.content[:3]==b"\xff\xd8\xff"
    assert source.is_file()
    assert client.delete(f"/api/clips/{clip['id']}").status_code==204
    assert client.get(url).status_code==404


def test_thumbnail_still_requires_auth(client,source):
    m=upload_file(client,source)
    clip=client.post(f"/api/media/{m['id']}/clips",
        json={"segments":[{"start":0,"end":3}]}).json()
    with TestClient(app) as other:
        assert other.get(f"/api/clips/{clip['id']}/thumbnail").status_code==401


def test_v5_review_embeds_real_thumbnails():
    js=(Path(__file__).resolve().parents[1]/
        "clipra"/"site"/"app-v5.js").read_text()
    assert "'/thumbnail'" in js
    assert "Source frame" in js
