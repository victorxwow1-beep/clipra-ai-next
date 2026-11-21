import hashlib
import json
import subprocess
from pathlib import Path

class MediaError(ValueError): pass

def ffprobe(source: Path):
    cmd=['ffprobe','-protocol_whitelist','file,pipe','-v','error','-show_entries','format=duration,format_name:stream=codec_type,codec_name,width,height,avg_frame_rate','-of','json',str(source)]
    p=subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    if p.returncode: raise MediaError('Could not decode source media')
    obj=json.loads(p.stdout)
    v=next((s for s in obj.get('streams',[]) if s.get('codec_type')=='video'),None)
    if not v: raise MediaError('The file has no video stream')
    try: duration=float(obj['format']['duration'])
    except (KeyError,ValueError,TypeError): raise MediaError('Video duration missing')
    if not (0.1 < duration <= 24*3600*3): raise MediaError('Invalid or unsupported video duration')
    fps=v.get('avg_frame_rate','0/1')
    try:
        a,b=map(float,fps.split('/')); fps=a/b if b else 0
    except Exception: fps=0
    if not fps or fps>240: raise MediaError('Unsupported frame rate')
    return {'duration':duration,'width':int(v['width']),'height':int(v['height']),'fps':fps,
            'has_audio':any(x.get('codec_type')=='audio' for x in obj.get('streams',[])),
            'format':obj['format'].get('format_name','unknown')}

def sha256_file(source:Path):
    h=hashlib.sha256()
    with source.open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()

def verify_decodable(path:Path):
    meta=ffprobe(path)
    for t in [0.0,max(0.0,meta['duration']-0.15)]:
        p=subprocess.run(['ffmpeg','-protocol_whitelist','file,pipe','-v','error','-ss',str(t),'-i',str(path),'-frames:v','1','-f','null','-'],capture_output=True,timeout=90)
        if p.returncode:raise MediaError('A source frame could not be decoded')
    return meta