import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from .media import ffprobe, MediaError

class RenderError(RuntimeError): pass
class RenderCancelled(RuntimeError): pass

def run_ffmpeg(cmd, timeout, should_cancel=None):
    proc=subprocess.Popen(cmd,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
    started=time.monotonic()
    while True:
        try:
            _,stderr=proc.communicate(timeout=.6)
            return proc.returncode,stderr.decode('utf8',errors='replace')
        except subprocess.TimeoutExpired:
            if should_cancel and should_cancel():
                proc.terminate()
                try:proc.communicate(timeout=4)
                except subprocess.TimeoutExpired:proc.kill();proc.communicate()
                raise RenderCancelled('Render cancelled by user')
            if time.monotonic()-started>timeout:
                proc.kill();proc.communicate()
                raise RenderError('FFmpeg rendering timed out')

def validate_segments(segments, duration):
    if not segments or len(segments)>30: raise ValueError('Supply 1 to 30 timeline segments')
    for s in segments:
        if not isinstance(s,dict):raise ValueError('Invalid segment')
        try:a=float(s['start']); b=float(s['end'])
        except (ValueError,TypeError,KeyError):raise ValueError('Invalid segment boundaries')
        if not (0 <= a < b <= duration+0.025) or b-a<0.2:raise ValueError('Segment outside source or too short')
    if sum(float(s['end'])-float(s['start']) for s in segments)>3*3600:raise ValueError('Export exceeds three hours')

def render_clip(source:Path, dest:Path, segments:list, *, crf:int=20, ratio:str='original', mode:str='fit', should_cancel=None):
    source=Path(source); dest=Path(dest)
    meta=ffprobe(source)
    validate_segments(segments,meta['duration'])
    if crf not in range(16,29): raise ValueError('Invalid CRF quality')
    allowed={'original':None,'9:16':(1080,1920),'16:9':(1920,1080),'4:3':(1440,1080),'3:4':(1080,1440),'1:1':(1080,1080)}
    if ratio not in allowed or mode not in ('fit','fill'):raise ValueError('Unsupported framing')
    if allowed[ratio]:
        w,h=allowed[ratio]
        vf=(f'scale={w}:{h}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2' if mode=='fit'
          else f'scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h}')
    else: vf='scale=trunc(iw/2)*2:trunc(ih/2)*2'
    dest.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(dir=dest.parent) as tmp:
        tmp=Path(tmp)
        items=[]
        for i,span in enumerate(segments):
            start=float(span['start']); length=float(span['end'])-start
            part=tmp/f'{i:03}.mp4'
            cmd=['ffmpeg','-hide_banner','-nostdin','-loglevel','error','-y','-ss',f'{start:.5f}','-protocol_whitelist','file,pipe','-i',str(source),'-t',f'{length:.5f}',
                 '-map','0:v:0','-map','0:a:0?','-vf',vf,'-c:v','libx264','-preset','fast','-crf',str(crf),'-pix_fmt','yuv420p',
                 '-c:a','aac','-b:a','192k','-ar','48000','-ac','2','-movflags','+faststart',str(part)]
            rc,stderr=run_ffmpeg(cmd,max(180,int(length*10)),should_cancel)
            if rc or not part.exists():raise RenderError('FFmpeg failed: '+stderr[-1500:])
            items.append(part)
        concat=tmp/'segments.txt'
        # These paths are generated inside an owned temporary directory (not user input)
        concat.write_text(''.join("file '"+str(p)+"'\n" for p in items))
        output=tmp/'result.mp4'
        cmd=['ffmpeg','-hide_banner','-nostdin','-loglevel','error','-y','-f','concat','-safe','0','-protocol_whitelist','file,pipe','-i',str(concat),'-c','copy','-movflags','+faststart',str(output)]
        rc,stderr=run_ffmpeg(cmd,max(180,int(sum(float(s['end'])-float(s['start']) for s in segments)*5)),should_cancel)
        if rc:raise RenderError('MP4 assembly failed: '+stderr[-1000:])
        check=ffprobe(output)
        expected=sum(float(s['end'])-float(s['start']) for s in segments)
        if abs(check['duration']-expected)>max(.3,.05*expected):raise RenderError('Rendered MP4 duration does not match edit')
        os.replace(output,dest)
        return {'output':str(dest),'duration':check['duration'], 'width':check['width'], 'height':check['height'],'has_audio':check['has_audio']}