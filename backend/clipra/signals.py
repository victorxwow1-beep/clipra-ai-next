"""Cheap bounded-memory A/V candidate discovery before multimodal model calls.

These are *signal candidates*, never semantic highlights. Sudden movement or a
loud sound is NOT proof of an event, win, complete scene, or editorial merit.
The real multimodal model must inspect candidate windows and decide.
"""
from __future__ import annotations
import subprocess
from pathlib import Path
import numpy as np

class SignalScanError(RuntimeError): pass


def _start(cmd):
    return subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                            stdin=subprocess.DEVNULL, bufsize=0)


def visual_activity(source: Path, duration: float, sample_fps: float=1.0):
    width,height=96,54
    cmd=['ffmpeg','-hide_banner','-nostdin','-loglevel','error','-protocol_whitelist','file,pipe',
         '-i',str(source),'-map','0:v:0','-vf',f'fps={sample_fps},scale={width}:{height}:flags=fast_bilinear,format=gray',
         '-an','-f','rawvideo','-pix_fmt','gray','pipe:1']
    proc=_start(cmd);previous=None;out=[];frame_size=width*height
    try:
        index=0
        while True:
            packet=bytearray()
            while len(packet)<frame_size:
                raw=proc.stdout.read(frame_size-len(packet))
                if not raw:break
                packet.extend(raw)
            if len(packet)!=frame_size:break
            arr=np.frombuffer(packet,dtype=np.uint8).astype(np.int16)
            diff=float(np.mean(np.abs(arr-previous))) if previous is not None else 0.0
            out.append((index/sample_fps,diff));index+=1
            previous=arr
        if proc.wait(timeout=30)!=0:raise SignalScanError('FFmpeg visual signal scan failed')
        return out
    finally:
        if proc.poll() is None:proc.kill();proc.wait()


def audio_activity(source:Path, duration:float):
    cmd=['ffmpeg','-hide_banner','-nostdin','-loglevel','error','-protocol_whitelist','file,pipe',
         '-i',str(source),'-map','0:a:0?','-vn','-ac','1','-ar','8000',
         '-f','s16le','pipe:1']
    proc=_start(cmd);out=[];index=0;stride=16000
    try:
        while True:
            packet=bytearray()
            while len(packet)<stride:
                raw=proc.stdout.read(stride-len(packet))
                if not raw:break
                packet.extend(raw)
            if len(packet)<2:break
            arr=np.frombuffer(bytes(packet[:len(packet)//2*2]),dtype=np.int16).astype(np.float32)
            rms=float(np.sqrt(np.mean((arr/32768.0)**2))) if len(arr) else 0.0
            out.append((float(index),rms));index+=1
            if len(packet)<stride:break
        if proc.wait(timeout=30)!=0:raise SignalScanError('FFmpeg audio signal scan failed')
        return out
    finally:
        if proc.poll() is None:proc.kill();proc.wait()


def discover_signals(source: Path, duration:float, *, max_events:int=24):
    """Return source timestamp + signal evidence, not claimed events.

    All decoding flows through FFmpeg streaming pipes; never reads the entire
    media or its derived frames into RAM. Does not call an external AI service.
    """
    source=Path(source)
    visual=visual_activity(source,duration)
    from .media import ffprobe
    audio=audio_activity(source,duration) if ffprobe(source)['has_audio'] else []
    import math
    scores={}
    for t,v in visual:
        sec=int(t)
        scores.setdefault(sec,{'visual':0.,'audio':0.})['visual']=min(1.0,float(v)/42.0)
    for t,v in audio:
        scores.setdefault(int(t),{'visual':0.,'audio':0.})['audio']=min(1.0,float(v)/.2)
    # Peaks can be used to CHOOSE where to spend semantic inference, not to
    # assert that an actual scene deserves a final edited clip.
    peaks=[]
    for sec,signal in scores.items():
        score=.65*signal['visual']+.35*signal['audio']
        if score>.17:peaks.append({'time':float(sec),'activity_score':round(score,4),
           'signals':{'frame_change':round(signal['visual'],4),'audio_level':round(signal['audio'],4)}})
    selected=[]
    for p in sorted(peaks,key=lambda x:x['activity_score'],reverse=True):
        if all(abs(p['time']-x['time'])>=6 for x in selected):selected.append(p)
        if len(selected)>=max_events:break
    return sorted(selected,key=lambda x:x['time'])


def select_analysis_windows(duration:float, signal_candidates:list[dict], max_windows:int, *, window_seconds:float=90.0, overlap:float=8.0):
    """Select bounded windows; selection DOES NOT imply exhaustive coverage.

    For short videos all windows are examined; for long sources the strongest
    content-agnostic activity peaks get expensive multimodal attention first.
    """
    if max_windows<1:raise ValueError('max_windows must be positive')
    starts=[];cursor=0.
    while cursor<duration:
        starts.append(cursor)
        if cursor+window_seconds>=duration:break
        cursor+=window_seconds-overlap
    if len(starts)<=max_windows:return starts,{'full_coverage':True,'total_windows':len(starts)}
    # Do not pretend quiet speech or meaningful drama must have strong motion.
    # When no cheap candidates are available, use evenly distributed coverage
    # and mark it as partial, so a real user can opt into extra analysis later.
    chosen=[]
    for p in sorted(signal_candidates,key=lambda x:x.get('activity_score',0),reverse=True):
        t=float(p['time'])
        start=max(0.,min(duration-window_seconds,t-window_seconds*.4))
        if all(abs(start-s)>=window_seconds-overlap for s in chosen):chosen.append(start)
        if len(chosen)>=max_windows:break
    if not chosen:
        for i in range(max_windows):chosen.append(max(0.,min(duration-window_seconds, duration*(i+.5)/max_windows-window_seconds*.5)))
    return sorted(chosen),{'full_coverage':False,'total_windows':len(starts),
                           'selected_windows':len(chosen),'selection':'audiovisual_activity_candidates_not_semantic_events'}