"""Real offline faster-whisper inference QA with synthetic, original speech.

Unlike monkeypatched unit tests, this test downloads real public model
weights, decodes a real AAC audio/video recording and performs CPU int8
inference. Uses original TTS prose created solely for this test.
"""
from __future__ import annotations
import os
import subprocess
import tempfile
from pathlib import Path

from clipra.local_speech import transcribe_local


SPEECH=(
    "When a creator records a long video, the best clips need context before and "
    "after the main event. The beginning should make sense and the ending should "
    "feel complete. We should not cut randomly in the middle of a story. "
    "The creator can review and edit each suggestion before downloading. "
    "A real clip should preserve the original spoken audio."
)


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="clipra-whisper-check-") as base:
        root=Path(base)
        wav=root/"spoken.wav"
        source=root/"spoken.mp4"
        subprocess.run(["espeak-ng","-s","125","-v","en-us","-w",str(wav),
                        SPEECH+" "+SPEECH],check=True,timeout=30)
        subprocess.run([
            "ffmpeg","-hide_banner","-loglevel","error","-y",
            "-f","lavfi","-i","color=c=black:s=320x180:r=8",
            "-i",str(wav),"-shortest","-c:v","libx264","-preset","ultrafast",
            "-pix_fmt","yuv420p","-c:a","aac","-b:a","128k",str(source)
        ],check=True,timeout=75)
        output=subprocess.check_output([
            "ffprobe","-v","error","-show_entries","format=duration",
            "-of","default=nw=1:nk=1",str(source)],text=True)
        duration=float(output.strip())
        os.environ["LOCAL_WHISPER_MODEL"]="tiny"
        os.environ["MAX_LOCAL_SPEECH_SECONDS"]="1800"
        os.environ["WHISPER_CACHE_DIR"]=str(root/"models")
        found, meta=transcribe_local(source,duration,max_clips=5,
                                      clip_length=30,category="podcast")
        assert meta["model"]=="faster-whisper/tiny",meta
        assert meta["segments_transcribed"]>0,(
            "Real Whisper did not recognize any spoken segment. "
            f"Duration={duration:.1f}; model={meta}")
        assert meta["language"].startswith("en"),meta
        assert all(x["origin"]=="local_speech" and x["end"]<=duration for x in found)
        print("REAL WHISPER MODEL VERIFIED",{
            "duration":round(duration,2),"language":meta["language"],
            "segments":meta["segments_transcribed"],"clips_found":len(found),
            "model":meta["model"],
        })


if __name__=="__main__":
    main()
