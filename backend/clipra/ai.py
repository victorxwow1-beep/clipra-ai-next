"""Actual multimodal file inference. Never fabricates highlights when no provider is configured."""
import os
import time
import tempfile
import subprocess
from pathlib import Path
from pydantic import BaseModel, Field

class AIUnavailable(RuntimeError): pass

class Moment(BaseModel):
    start: float = Field(ge=0)
    end: float = Field(gt=0)
    title: str
    event: str
    visual_evidence: str
    audio_evidence: str = ''
    reason: str
    confidence: float = Field(ge=0,le=1)

class MomentBatch(BaseModel):
    moments: list[Moment]

CATEGORY_GUIDANCE={
    'gaming':'Complete actual gameplay incidents, surprising outcomes, humor and wins. Ignore generic HUD, unrelated notifications and assumed achievements.',
    'podcast':'Coherent question-answer exchanges, complete statements and true insight; keep context.',
    'livestream':'Meaningful interactions, resolved incidents and reactions; omit idle chatter and notifications.',
    'education':'Self-contained explanations, examples and demonstrable lessons; no misleading fragment.',
    'drama':'Preserve characters, cause-and-effect, dialogue continuity and a natural resolution.',
    'general':'Use topic-specific criteria and clear context; do not assume dramatic events without evidence.'
}

def analyze_video(source:Path, duration:float, category:str, max_clips:int, *, max_windows:int|None=None):
    api_key=os.getenv('GEMINI_API_KEY')
    if not api_key:raise AIUnavailable('GEMINI_API_KEY not configured; real semantic analysis cannot run')
    if os.getenv('ALLOW_EXTERNAL_AI','false').lower()!='true':
        raise AIUnavailable('External AI disabled by server operator (ALLOW_EXTERNAL_AI=true required)')
    from .gemini_rest import GeminiVideoREST,GeminiProviderError
    model=os.getenv('GEMINI_VIDEO_MODEL','gemini-3.5-flash')
    from .signals import discover_signals,select_analysis_windows
    window_seconds=90
    limit=max_windows or int(os.getenv('MAX_AI_WINDOWS','4'))
    # Cheap local signal scan narrows expensive video windows on LONG sources.
    # Audio/visual activity only discovers CANDIDATES; the model must still
    # inspect the actual source window and verify its meaning and continuity.
    total_estimated=max(1,__import__('math').ceil(max(0,duration-window_seconds)/(window_seconds-8))+1)
    signal_candidates=discover_signals(source,duration) if total_estimated>limit else []
    starts,coverage=select_analysis_windows(duration,signal_candidates,limit,window_seconds=window_seconds)

    # A model metadata lookup is a preflight, NOT proof of video capabilities.
    try:
        with GeminiVideoREST(api_key,model) as preflight:preflight.model_metadata()
    except GeminiProviderError as e:raise AIUnavailable(str(e)) from e

    evidence=[];counts={'input_tokens':0,'output_tokens':0,'model':model,'windows':len(starts),'coverage':coverage,'activity_candidates':len(signal_candidates)}
    for start in starts:
        length=min(window_seconds,duration-start)
        with tempfile.TemporaryDirectory() as tmp:
            proxy=Path(tmp)/'window.mp4'
            cmd=['ffmpeg','-hide_banner','-loglevel','error','-nostdin','-y','-ss',str(start),'-protocol_whitelist','file,pipe','-i',str(source),'-t',str(length),
                 '-vf','scale=480:-2,fps=3','-c:v','libx264','-preset','ultrafast','-crf','30','-c:a','aac','-b:a','64k',str(proxy)]
            p=subprocess.run(cmd,capture_output=True,text=True,timeout=max(120,int(length*6)))
            if p.returncode or not proxy.exists():raise AIUnavailable('Video proxy generation failed; actual video was not analyzed')
            uploaded=None
            try:
                with GeminiVideoREST(api_key,model) as provider:
                    try:
                        uploaded,uri=provider.upload_video(proxy)
                        prompt=("You are a critical professional video editor. Inspect the ACTUAL video frames and audio. "
                            "Return only noteworthy self-contained, contextual moments. NEVER invent observations, achievements or dialogue. "
                            "The timestamps MUST be relative to this uploaded window (0 through its duration). "
                            "No events is a valid answer. Preserve correct event sequence, setup and payoff; be conservative. "
                            "Each visual_evidence must describe something genuinely seen and audio_evidence something genuinely heard (or blank). "
                            "Only source-backed claims. Never cut in the middle of an action or spoken statement. "
                            f"Category: {category}. Criteria: {CATEGORY_GUIDANCE.get(category,CATEGORY_GUIDANCE['general'])}. "
                            f"Window duration: {length:.2f}s. Return UP TO {max_clips} strong moments, 0 is valid.")
                        content,usage=provider.infer(uri,prompt,MomentBatch.model_json_schema())
                        parsed=MomentBatch.model_validate_json(content)
                        for m in parsed.moments:
                            if m.end>length+.5 or m.start>=m.end or m.confidence<.65 or not m.visual_evidence.strip():continue
                            evidence.append({'start':round(m.start+start,3),'end':round(min(duration,m.end+start),3),
                              'title':m.title[:160],'event':m.event,'reason':m.reason,
                              'evidence':{'visual':m.visual_evidence,'audio':m.audio_evidence},'confidence':m.confidence})
                        counts['input_tokens']+=int(usage.get('promptTokenCount',0) or 0)
                        counts['output_tokens']+=int(usage.get('candidatesTokenCount',0) or 0)
                    finally:
                        if uploaded:provider.delete_file(uploaded)
            except GeminiProviderError as e:
                raise AIUnavailable(str(e)) from e
    # Remove overlapping suggestions, selecting stronger independently observed moments.
    accepted=[]
    for m in sorted(evidence,key=lambda x:x['confidence'],reverse=True):
        if any(max(0,min(m['end'],e['end'])-max(m['start'],e['start'])) / min(m['end']-m['start'],e['end']-e['start'])>.55 for e in accepted):continue
        accepted.append(m)
        if len(accepted)>=max_clips:break
    return sorted(accepted,key=lambda x:x['start']),counts