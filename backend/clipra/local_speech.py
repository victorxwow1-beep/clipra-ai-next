"""CLIPRA's offline transcript path uses SYSTRAN/faster-whisper (MIT).

This is actual speech recognition from the user's original audio, not
invented dialogue. The selection algorithm finds coherent spoken stretches,
not a semantic claim that every selected moment is entertaining.
"""
from __future__ import annotations
import math
import os
from pathlib import Path


class LocalSpeechUnavailable(RuntimeError):
    pass


def speech_moments(duration: float, segments: list[dict], *,
                   max_clips: int = 5, clip_length: float = 24,
                   category: str = "podcast") -> list[dict]:
    if not math.isfinite(duration) or duration <= 0:
        return []
    max_clips = min(max(int(max_clips), 1), 12)
    clip_length = min(duration, max(10.0, min(float(clip_length), 1800.0)))
    cleaned = []
    for seg in segments:
        try:
            a, b = float(seg["start"]), float(seg["end"])
            phrase = " ".join(str(seg["text"]).split()).strip()
        except (KeyError, TypeError, ValueError):
            continue
        if not (0 <= a < b <= duration + 0.25) or len(phrase.split()) < 3:
            continue
        cleaned.append({"start":a,"end":min(b,duration),"text":phrase})
    cleaned.sort(key=lambda x: x["start"])
    if not cleaned:
        return []
    windows = []
    for i, seg in enumerate(cleaned):
        if seg["start"] > duration - 4:
            continue
        start = max(0.0, seg["start"] - 1.4)
        end_limit = min(duration,start+clip_length)
        excerpt = []
        last_end = seg["start"]
        for part in cleaned[i:]:
            if part["start"] > end_limit or part["start"]-last_end > 4.0:
                break
            if part["end"] > end_limit + 0.3:
                break
            excerpt.append(part)
            last_end = part["end"]
        if not excerpt:
            continue
        body = " ".join(x["text"] for x in excerpt)
        words = len(body.split())
        span = last_end - excerpt[0]["start"]
        if words < 12 or span < 5 or words / max(1,span) < .8:
            continue
        sentence_ends = sum(x["text"].rstrip().endswith((".","?","!")) for x in excerpt)
        # Give priority to coherent complete speech and exchanges, without
        # assuming a transcript mentions events that are not audible.
        if sentence_ends < 1:
            continue
        score = min(words, 90) / 90 + .2 * min(sentence_ends,3)
        if category == "education" and any(
            term in body.lower() for term in ("because","for example","means","therefore","how to","step")):
            score += .18
        if category == "podcast" and "?" in body and sentence_ends > 1:
            score += .18
        if start < 4 or duration - last_end < 4:
            score -= .3
        windows.append({
            "start": round(start,3), "end":round(min(duration,last_end+1.1),3),
            "score": score, "title":"Spoken moment",
            "reason": f"Actual locally transcribed speech: {body[:210]}. Review the complete context and both cut boundaries.",
            "origin":"local_speech",
        })
    selected=[]
    for candidate in sorted(windows,key=lambda x:x["score"],reverse=True):
        overlap=lambda a,b: max(0,min(a["end"],b["end"])-max(a["start"],b["start"]))
        if any(overlap(candidate,prev) > .25*min(prev["end"]-prev["start"], candidate["end"]-candidate["start"])
               for prev in selected):
            continue
        selected.append({k:v for k,v in candidate.items() if k!="score"})
        if len(selected)>=max_clips:
            break
    return sorted(selected,key=lambda x:x["start"])


def transcribe_local(source: Path, duration: float, *,
                     max_clips: int, clip_length: float, category: str):
    """Run genuine local Whisper inference using CPU int8, with resource caps."""
    limit = float(os.getenv("MAX_LOCAL_SPEECH_SECONDS", "1800"))
    if duration > limit:
        raise LocalSpeechUnavailable(
            f"Free local speech model limit is {int(limit//60)} minutes per source. "
            "Longer sources need chunked processing and more hosting capacity.")
    try:
        from faster_whisper import WhisperModel
    except ImportError as e:
        raise LocalSpeechUnavailable("Local faster-whisper model is not installed.") from e
    name=os.getenv("LOCAL_WHISPER_MODEL","tiny")
    allowed={"tiny","base","small"}
    if name not in allowed:
        raise LocalSpeechUnavailable("Unsupported speech model. Configure tiny, base, or small.")
    try:
        model=WhisperModel(name, device="cpu", compute_type="int8",
                           download_root=os.getenv("WHISPER_CACHE_DIR") or None,
                           local_files_only=os.getenv("WHISPER_OFFLINE","false").lower()=="true",
                           cpu_threads=max(1,min(int(os.getenv("WHISPER_CPU_THREADS","2")),4)))
        it,info=model.transcribe(str(source),beam_size=2,
                                  vad_filter=True, condition_on_previous_text=False)
        raw=[{"start":float(x.start),"end":float(x.end),"text":x.text}
             for x in it]
    except Exception as e:
        raise LocalSpeechUnavailable(
            "Local speech analysis could not start or complete on this host. "
            "Check the model download, RAM and CPU limits. No fake clips were generated."
        ) from e
    found=speech_moments(duration,raw,max_clips=max_clips,
                         clip_length=clip_length,category=category)
    return found, {
        "model":f"faster-whisper/{name}", "segments_transcribed":len(raw),
        "language":str(info.language), "candidate_count":len(found),
        "scope":"actual_local_transcript_not_multimodal_video_understanding",
    }
