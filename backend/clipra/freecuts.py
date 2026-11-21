"""Free, local audio/visual draft selection. No external model, no token billing.

IMPORTANT: high activity is NOT semantic understanding. Never claim a proposed
window has an actual gaming win, punchline, useful sentence, or "viral" quality.
"""
from __future__ import annotations

import math


def propose_drafts(duration: float, signals: list[dict], max_clips: int = 4,
                   clip_length: float = 22.0) -> list[dict]:
    if not math.isfinite(duration) or duration <= 0:
        return []
    max_clips = max(1, min(int(max_clips), 12))
    clip_length = min(max(5.0, float(clip_length)), duration)
    # Audio and motion spikes are only a rough indicator. Offset the start
    # so the user can review the lead-in before publishing.
    windows: list[dict] = []
    for peak in sorted(signals, key=lambda item: item.get("activity_score", 0), reverse=True):
        try:
            t = float(peak["time"])
            score = float(peak["activity_score"])
        except (TypeError, ValueError, KeyError):
            continue
        if not math.isfinite(t) or not math.isfinite(score) or score < 0.17:
            continue
        start = max(0.0, min(duration - clip_length, t - clip_length * 0.32))
        end = start + clip_length
        if any(min(end, item["end"]) - max(start, item["start"]) > clip_length * 0.3
               for item in windows):
            continue
        windows.append({
            "title": f"Activity draft {len(windows) + 1}",
            "start": round(start, 3),
            "end": round(end, 3),
            "confidence": None,
            "reason": ("Local motion/audio activity near "
                       f"{int(t // 60)}:{int(t % 60):02d}. Review manually: "
                       "activity does not prove a meaningful or complete moment."),
            "origin": "signal_draft",
        })
        if len(windows) >= max_clips:
            break
    if len(windows) < max_clips:
        # If nothing peaks, provide clearly labelled evenly distributed DRAFTS.
        # Never fabricate events or assign fake AI confidence.
        n = max_clips
        for i in range(n):
            start = max(0.0, (duration - clip_length) * ((i + 0.5) / n)
                        - clip_length * 0.5)
            start = min(start, duration - clip_length)
            end = start + clip_length
            if any(min(end, item["end"]) - max(start, item["start"]) > clip_length * 0.3
                   for item in windows):
                continue
            windows.append({
                "title": f"Review draft {len(windows) + 1}",
                "start": round(start, 3),
                "end": round(end, 3),
                "confidence": None,
                "reason": ("Evenly spaced local fallback. No scene was verified; "
                           "review source footage and refine both boundaries."),
                "origin": "signal_draft",
            })
            if len(windows) >= max_clips:
                break
    return sorted(windows, key=lambda item: item["start"])
