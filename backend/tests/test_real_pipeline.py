import json
import os
import struct
import subprocess
from pathlib import Path
from clipra.db import Session
from clipra.models import Job
from clipra.media import ffprobe, sha256_file
from clipra.worker import run_pending
from .conftest import upload_file

def test_auth_and_rights(client):
    assert client.post('/api/uploads',json={'filename':'x.mp4','size':100,'rights_confirmed':False}).status_code==400
    assert client.post('/api/auth/login',json={'password':'bad-password'}).status_code==401

def test_real_60s_video_to_playable_mp4(client,source):
    m=upload_file(client,source,chunk=850*1024,interrupt=True)
    assert 59.9<=m['duration']<=60.1
    assert m['sha256']==sha256_file(source)
    assert m['has_audio'] is True
    # An explicit manual EDL is honest: no AI conclusions are claimed from a synthetic clip.
    r=client.post(f'/api/media/{m["id"]}/clips',json={'title':'Manual verified cut',
      'segments':[{'start':5,'end':11},{'start':22,'end':28}], 'ratio':'original','mode':'fit','crf':20})
    assert r.status_code==201,r.text
    clip=r.json();assert clip['rendered'] is False
    r=client.post(f'/api/clips/{clip["id"]}/render');assert r.status_code==202
    assert run_pending(max_jobs=1)==1
    state=client.get(f'/api/jobs/{r.json()["id"]}').json()
    assert state['status']=='done',state
    d=client.get(f'/api/clips/{clip["id"]}/download')
    assert d.status_code==200 and d.content[:4] != b'' and len(d.content)>10000
    output=Path(os.environ['MEDIA_ROOT'])/'qa-export.mp4';output.write_bytes(d.content)
    meta=ffprobe(output)
    assert 11.7<=meta['duration']<=12.3,meta
    assert meta['has_audio'] and meta['width']==320 and meta['height']==180
    data=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-of','json',str(output)]))
    assert any(s['codec_name']=='h264' for s in data['streams'])
    assert any(s['codec_name']=='aac' for s in data['streams'])
    decode=subprocess.run(['ffmpeg','-v','error','-i',str(output),'-f','null','-'],capture_output=True,timeout=120)
    assert decode.returncode==0,decode.stderr.decode()[-500:]
    assert sha256_file(source)==m['sha256']

def test_69_5_megabyte_upload_and_render(client,source,tmp_path):
    # Valid synthetic MP4 with an MP4 `free` atom to exercise the full upload size path.
    # Media bitrate is NOT equivalent to a real 69.5 MiB capture; disclosed in QA report.
    path=tmp_path/'69_5mb_container.mp4'
    raw=source.read_bytes();target=round(69.5*1024*1024)
    padding=target-len(raw)
    assert padding>8
    with path.open('wb') as f:
        f.write(raw)
        f.write(struct.pack('>I4s',padding,b'free'))
        f.truncate(target)
    assert path.stat().st_size==target
    assert ffprobe(path)['duration']>59
    m=upload_file(client,path,chunk=4*1024*1024,interrupt=True)
    assert m['size']==target
    r=client.post(f'/api/media/{m["id"]}/clips',json={'title':'70MB upload regression','segments':[{'start':1,'end':3}]})
    assert r.status_code==201,r.text
    j=client.post(f'/api/clips/{r.json()["id"]}/render');assert j.status_code==202
    assert run_pending(max_jobs=1)==1
    assert client.get(f'/api/jobs/{j.json()["id"]}').json()['status']=='done'
    assert len(client.get(f'/api/clips/{r.json()["id"]}/download').content)>1000

def test_real_ai_is_blocked_without_key(client,source):
    m=upload_file(client,source,chunk=2*1024*1024)
    assert client.post(f'/api/media/{m["id"]}/analyze',json={'consent':False}).status_code==400
    r=client.post(f'/api/media/{m["id"]}/analyze',json={'consent':True,'max_clips':3,'category':'gaming'})
    assert r.status_code==202
    run_pending(max_jobs=1)
    j=client.get(f'/api/jobs/{r.json()["id"]}').json()
    assert j['status']=='blocked' and 'GEMINI_API_KEY' in j['error']
    assert client.get(f'/api/media/{m["id"]}/clips').json()==[]

def test_youtube_never_claims_media(client):
    r=client.post('/api/youtube/inspect',json={'url':'https://www.youtube.com/watch?v=dQw4w9WgXcQ'})
    assert r.status_code==200 and r.json()['media_bytes_available'] is False
    assert client.post('/api/youtube/inspect',json={'url':'https://example.com/x'}).status_code==422

def test_bad_video_file_rejected(client,tmp_path):
    f=tmp_path/'fake.mp4';f.write_bytes(b'not a video'*100)
    r=client.post('/api/uploads',json={'filename':'fake.mp4','size':f.stat().st_size,'rights_confirmed':True})
    uid=r.json()['id'];client.patch(f'/api/uploads/{uid}',data=f.read_bytes(),headers={'Upload-Offset':'0'})
    assert client.post(f'/api/uploads/{uid}/complete').status_code==415

def test_upload_offset_and_duplicate_analysis_handling(client,source):
    r=client.post('/api/uploads',json={'filename':source.name,'size':source.stat().st_size,'rights_confirmed':True})
    uid=r.json()['id']
    assert client.patch(f'/api/uploads/{uid}',data=b'garbage',headers={'Upload-Offset':'4'}).status_code==409
    assert client.head(f'/api/uploads/{uid}').headers['upload-offset']=='0'
    pathbytes=source.read_bytes()
    assert client.patch(f'/api/uploads/{uid}',data=pathbytes,headers={'Upload-Offset':'0'}).status_code==204
    m=client.post(f'/api/uploads/{uid}/complete').json()
    payload={'consent':True,'category':'general','max_clips':2}
    a=client.post(f'/api/media/{m["id"]}/analyze',json=payload).json()
    b=client.post(f'/api/media/{m["id"]}/analyze',json=payload).json()
    assert a['id']==b['id']
    assert client.post(f'/api/jobs/{a["id"]}/cancel').json()['status']=='cancelled'
    assert client.get(f'/api/jobs/{a["id"]}').json()['status']=='cancelled'
    assert client.post(f'/api/media/{m["id"]}/clips',json={'segments':[{'start':40,'end':70}]}).status_code==422

def test_export_fit_9_16(client,source):
    m=upload_file(client,source)
    r=client.post(f'/api/media/{m["id"]}/clips',json={'title':'Mobile portrait padding',
        'segments':[{'start':1,'end':2.2}],'ratio':'9:16','mode':'fit','crf':24})
    assert r.status_code==201,r.text
    j=client.post(f'/api/clips/{r.json()["id"]}/render').json()
    assert run_pending(max_jobs=1)==1
    status=client.get(f'/api/jobs/{j["id"]}').json()
    assert status['status']=='done',status
    out=Path(os.environ['MEDIA_ROOT'])/'exports'/f'{r.json()["id"]}.mp4'
    probe=ffprobe(out)
    assert (probe['width'],probe['height'])==(1080,1920)