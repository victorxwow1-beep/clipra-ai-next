"""Free local OCR evidence verification for CLIPRA v4-style gameplay editing.

Only actual source-frame text is accepted. This module does NOT identify player
kills from motion, infer unseen victories, or claim full video understanding.
"""
from __future__ import annotations
import math
import re
import shutil
import subprocess
from pathlib import Path

RULES = [
    ("player_elimination", re.compile(r"\b(?:you|your|i)\s+(?:have\s+)?(?:killed|eliminated|defeated|knocked(?:\s+out)?|finished|took\s+down)\b", re.I)),
    ("match_win", re.compile(r"\b(?:winner\s+winner\s+chicken\s+dinner|victory\s*(?:royale)?|match\s+won|you\s+win|you\s+won)\b", re.I)),
]

def classify_hud_text(text: str):
    normalized = " ".join(str(text).replace("\n", " ").split())[:400]
    for kind, pattern in RULES:
        match = pattern.search(normalized)
        if match:
            return {"kind": kind, "evidence": normalized, "matched": match.group(0)}
    return None


def extract_ocr_text(path: Path, sec: float, *, timeout: int = 16) -> str:
    if not shutil.which("tesseract") or not shutil.which("ffmpeg"):
        raise RuntimeError("Local OCR unavailable: FFmpeg and Tesseract required")
    frame = subprocess.run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin",
         "-ss", f"{sec:.3f}", "-i", str(path), "-frames:v", "1",
         "-vf", "scale=w=1280:h=720:force_original_aspect_ratio=decrease:flags=lanczos",
         "-f", "image2pipe", "-vcodec", "png", "pipe:1"],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout, check=False)
    if frame.returncode or not frame.stdout:
        return ""
    text = subprocess.run(["tesseract", "stdin", "stdout", "--psm", "11"],
                          input=frame.stdout, stdout=subprocess.PIPE,
                          stderr=subprocess.DEVNULL, timeout=timeout, check=False)
    return text.stdout.decode("utf-8", errors="replace")[:1200] if text.returncode == 0 else ""


def sample_times(duration: float, candidates: list[dict], *, max_frames: int = 45) -> list[float]:
    max_frames = max(5, min(int(max_frames), 90))
    if duration <= 0 or not math.isfinite(duration):
        return []
    step = max(1.0, duration / max(1, max_frames // 2))
    timeline = [min(duration - .1, step * (i + .5))
                for i in range(max(1, int(math.ceil(duration / step))))]
    ranked = sorted(candidates, key=lambda x: x.get("activity_score", 0), reverse=True)
    peaks = []
    for item in ranked[:max_frames // 5]:
        try:
            t = float(item["time"])
        except (ValueError, TypeError, KeyError):
            continue
        peaks.extend([min(duration - .1, max(.1, t + delta)) for delta in (.6, 1.8)])
    result = []
    for t in peaks + timeline:
        if 0 <= t < duration and all(abs(t - x) > .6 for x in result):
            result.append(t)
        if len(result) >= max_frames:
            break
    return sorted(result)


def evidenced_moments(duration: float, observations: list[tuple[float, str]], *,
                      max_clips: int = 4, clip_length: float = 22) -> list[dict]:
    """Return zero clips when direct evidence is missing. Never force N clips."""
    if not math.isfinite(duration) or duration <= 0:
        return []
    clip_length = min(duration, max(10.0, min(float(clip_length), 60.0)))
    findings = []
    for sec, text in observations:
        event = classify_hud_text(text)
        if not event:
            continue
        if any(abs(sec - x["event_time"]) < 8 and event["kind"] == x["event_type"]
               for x in findings):
            continue
        start = max(0.0, min(duration - clip_length, sec - clip_length * .65))
        end = min(duration, start + clip_length)
        findings.append({
            "start": round(start, 3), "end": round(end, 3),
            "event_time": round(sec, 3), "event_type": event["kind"],
            "title": ("HUD-evidenced player outcome" if event["kind"] == "player_elimination"
                      else "HUD-evidenced match result"),
            "origin": "local_text_evidence", "confidence": None,
            "reason": (f"On-screen text near {int(sec) // 60}:{int(sec) % 60:02d}: "
                       f"{event['evidence'][:180]}. OCR evidence only; "
                       "review action, owner and context before posting."),
        })
    result = []
    for item in findings:
        if any(min(item["end"], other["end"]) - max(item["start"], other["start"])
               > .6 * min(item["end"] - item["start"],
                          other["end"] - other["start"]) for other in result):
            continue
        result.append(item)
        if len(result) >= max(1, min(int(max_clips), 12)):
            break
    return result


def analyze_hud_video(path: Path, duration: float, candidates: list[dict], *,
                      max_clips: int = 4, clip_length: float = 22, max_frames: int = 45):
    times = sample_times(duration, candidates, max_frames=max_frames)
    observations = [(t, extract_ocr_text(path, t)) for t in times]
    found = evidenced_moments(duration, observations,
                              max_clips=max_clips, clip_length=clip_length)
    return found, {
        "frames_checked": len(times), "duration_seconds": duration,
        "coverage": "sampled_only_not_exhaustive",
        "engine": "free_local_ffmpeg_tesseract_ocr",
        "semantic_limit": "visible_hud_text_only_not_complete_video_understanding",
    }
