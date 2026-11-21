"""Genuine MIT-licensed faster-whisper tiny weights + real generated human speech.

Unlike mock protocol tests this performs actual speech-to-text model inference.
Public open model is downloaded only in GitHub Actions; Docker bakes weights
offline for production. This is not a test of podcast editorial quality.
"""
from __future__ import annotations
import os
import shutil
import subprocess
from pathlib import Path
import pytest


@pytest.mark.skipif(os.getenv("RUN_REAL_WHISPER_TEST")!="1",
                    reason="External open model download is tested only in the dedicated CI gate")
def test_actual_open_model_transcribes_spoken_audio(tmp_path:Path):
    assert shutil.which("espeak-ng"), "Install espeak-ng for the real voice fixture"
    wav=tmp_path/"original-voice.wav"
    spoken=("This is a real recording about a video editor. "
            "The editor should preserve the original soundtrack and find important moments. "
            "We need to keep the full context and finish each sentence naturally. ")
    subprocess.run(["espeak-ng","-v","en-us","-s","128","-w",str(wav),
                    spoken*2],check=True,timeout=30)
    assert wav.stat().st_size>50000
    from faster_whisper import WhisperModel
    cache=tmp_path/"model-cache"
    model=WhisperModel("tiny",device="cpu",compute_type="int8",
                       download_root=str(cache),cpu_threads=2)
    segments,meta=model.transcribe(str(wav),beam_size=2,vad_filter=True,
                                  language="en",condition_on_previous_text=False)
    observed=[{"start":float(x.start),"end":float(x.end),"text":x.text}
              for x in segments]
    transcript=" ".join(x["text"] for x in observed).lower()
    print("Verified real model output:",transcript[:500])
    assert len(transcript.split())>=9, observed
    assert any(t in transcript for t in ("video","editor","original","recording")),transcript
    assert all(x["end"]>x["start"] for x in observed)
    assert meta.language=="en"
    # Confirm no additional online access is needed once weights are present.
    cached=WhisperModel("tiny",device="cpu",compute_type="int8",
                        download_root=str(cache),local_files_only=True,cpu_threads=2)
    rechecked,_=cached.transcribe(str(wav),beam_size=1,vad_filter=True,language="en")
    assert list(rechecked)
