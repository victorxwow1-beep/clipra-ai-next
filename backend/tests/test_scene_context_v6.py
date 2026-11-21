"""Real PySceneDetect scene boundaries + never trim genuine evidence off."""
import subprocess
from pathlib import Path

from clipra.scene_context import detect_scene_cuts, refine_scene_boundaries


def scene_video(tmp_path:Path):
    source=tmp_path/"two-scenes.mp4"
    subprocess.run(["ffmpeg","-hide_banner","-loglevel","error","-y",
        "-f","lavfi","-i","color=c=black:s=320x180:r=15:d=6",
        "-f","lavfi","-i","color=c=white:s=320x180:r=15:d=6",
        "-filter_complex","[0:v][1:v]concat=n=2:v=1:a=0[out]",
        "-map","[out]","-c:v","libx264","-preset","ultrafast",
        "-pix_fmt","yuv420p",str(source)],check=True,timeout=40)
    return source


def test_detect_real_source_visual_change_and_preserve_anchor(tmp_path):
    source=scene_video(tmp_path)
    cuts=detect_scene_cuts(source,12,start=5.5,end=10.5)
    assert any(abs(t-6.0)<=.15 for t in cuts),cuts
    original={"start":5.5,"end":10.5,"event_time":8.0,
              "origin":"local_text_evidence","title":"Evidence supported","reason":"Real text"}
    refined=refine_scene_boundaries(source,12,[original])
    assert len(refined)==1
    item=refined[0]
    assert abs(item["start"]-6.0)<=.15,item
    assert abs(item["end"]-11.0)<=.15,item
    assert abs((item["end"]-item["start"])-5)<.05,item
    assert item["start"]<original["event_time"]<item["end"]
    assert original["start"]==5.5  # original edit is never mutated


def test_speech_keeps_sentence_anchored_spans(tmp_path):
    source=scene_video(tmp_path)
    original={"start":5.5,"end":10.5,"origin":"local_speech",
              "reason":"Real transcript"}
    result=refine_scene_boundaries(source,12,[original])
    assert result[0]["start"]==5.5
    assert result[0]["end"]==10.5


def test_no_scene_does_not_create_fake_cut(tmp_path):
    source=scene_video(tmp_path)
    selection={"start":1,"end":3,"event_time":2,
               "origin":"local_text_evidence"}
    result=refine_scene_boundaries(source,12,[selection])
    assert result[0]["start"]==1 and result[0]["end"]==3
    assert result[0].get("scene_check")!="aligned_to_verified_scene_transition"
