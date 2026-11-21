import os
from pathlib import Path
os.environ['DATABASE_URL']='sqlite:////tmp/clipra-next-qa-'+str(os.getpid())+'.db'
os.environ['MEDIA_ROOT']='/tmp/clipra-next-qa-media-'+str(os.getpid())
os.environ['CLIPRA_ADMIN_PASSWORD']='a-long-test-workspace-password'
os.environ['CLIPRA_SESSION_SECRET']='a-test-session-secret-with-sufficient-length'
os.environ['ALLOW_EXTERNAL_AI']='false'
import pytest
from fastapi.testclient import TestClient
from clipra.main import app

@pytest.fixture(scope='session')
def client():
    with TestClient(app) as c:
        resp=c.post('/api/auth/login',json={'password':os.environ['CLIPRA_ADMIN_PASSWORD']})
        assert resp.status_code==200,resp.text
        yield c

@pytest.fixture(scope='session')
def source(tmp_path_factory):
    import subprocess
    path=tmp_path_factory.mktemp('video')/'source.mp4'
    cmd=['ffmpeg','-hide_banner','-loglevel','error','-y','-f','lavfi','-i','testsrc2=size=320x180:rate=15',
         '-f','lavfi','-i','sine=frequency=440:sample_rate=48000','-t','60','-c:v','libx264','-preset','ultrafast',
         '-crf','28','-pix_fmt','yuv420p','-c:a','aac','-b:a','96k','-movflags','+faststart',str(path)]
    subprocess.run(cmd,check=True,timeout=140)
    return path

def upload_file(c,path,chunk=1024*1024,interrupt=False):
    size=path.stat().st_size
    r=c.post('/api/uploads',json={'filename':path.name,'size':size,'rights_confirmed':True})
    assert r.status_code==201,r.text
    upload_id=r.json()['id'];offset=0
    with path.open('rb') as f:
        while True:
            part=f.read(chunk)
            if not part:break
            r=c.patch(f'/api/uploads/{upload_id}',data=part,headers={'Upload-Offset':str(offset),'Tus-Resumable':'1.0.0','Content-Type':'application/offset+octet-stream'})
            assert r.status_code==204,r.text
            offset=int(r.headers['upload-offset'])
            if interrupt and offset<size:
                h=c.head(f'/api/uploads/{upload_id}');assert int(h.headers['upload-offset'])==offset
                interrupt=False
    r=c.post(f'/api/uploads/{upload_id}/complete');assert r.status_code==200,r.text
    return r.json()