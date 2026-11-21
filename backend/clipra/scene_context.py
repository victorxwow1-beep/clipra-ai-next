"""Bounded, source-backed scene boundary refinement with PySceneDetect (BSD-3).

Scene changes improve trim boundaries but do not establish whether a moment is
interesting. Keep each evidence anchor and the chosen duration intact.
"""
from __future__ import annotations
import math
import os
from pathlib import Path


def detect_scene_cuts(source: Path, duration: float, start: float, end: float):
    from scenedetect import detect, ContentDetector
    lo=max(0.0,float(start)-1.8)
    hi=min(float(duration),float(end)+1.8)
    if hi-lo<1.0 or hi-lo>70.0:
        return []
    scenes=detect(str(source),
        ContentDetector(threshold=27.0,min_scene_len=12),
        start_time=lo,end_time=hi,start_in_scene=True)
    # The first/last scene edges may be supplied range bounds, not video cuts.
    return sorted(set(round(a.get_seconds(),3) for a,b in scenes[1:]
                      if lo+.15<a.get_seconds()<hi-.15))


def refine_scene_boundaries(source: Path, duration: float, moments: list[dict]):
    """Snap a *short* event clip to a nearby scene cut while keeping its duration.

    Speech highlights keep their transcribed sentence-aligned timestamps.
    When scene inspection fails, leave real evidence clips unchanged rather
    than making up boundaries or discarding good original footage.
    """
    max_clips=max(0,min(int(os.getenv("MAX_SCENE_REFINEMENTS","6")),12))
    results=[]
    for i,entry in enumerate(moments):
        item=dict(entry)
        start=float(item["start"]);end=float(item["end"])
        length=end-start
        if i>=max_clips or item.get("origin")!="local_text_evidence" or length<=0 or length>65:
            results.append(item);continue
        try:
            cuts=detect_scene_cuts(source,duration,start,end)
        except (Exception,):
            item["scene_check"]="failed_preserved_original_boundaries"
            results.append(item);continue
        # Do not change relative event context, and keep exact requested length.
        options=[p for p in cuts if abs(p-start)<=1.0]
        if options:
            adjusted=min(options,key=lambda p:abs(p-start))
            shift=adjusted-start
            new_start=start+shift;new_end=end+shift
            anchor=float(item.get("event_time",(start+end)/2))
            if (0<=new_start<new_end<=duration and
                new_start+0.5<=anchor<=new_end-0.5 and
                math.isfinite(new_start) and math.isfinite(new_end)):
                item["start"]=round(new_start,3)
                item["end"]=round(new_end,3)
                item["scene_check"]="aligned_to_verified_scene_transition"
            else:
                item["scene_check"]="scene_transition_rejected_to_preserve_event"
        else:
            item["scene_check"]="no_close_transition_original_context_preserved"
        results.append(item)
    return results
