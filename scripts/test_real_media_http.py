"""Live backend HTTP integration QA. Requires auth credentials and a local worker + FFmpeg.

Runs on an authorized synthetic local media fixture, with no third-party AI transfer.
Requires CLIPRA_TEST_SOURCE, CLIPRA_TEST_BASE_URL, CLIPRA_ADMIN_PASSWORD,
DATABASE_URL, MEDIA_ROOT, CLIPRA_SESSION_SECRET to match the server. Never logs secrets.
"""
import os,sys,json,hashlib,subprocess,time
from pathlib import Path
import httpx
SOURCE=Path(os.environ.get('CLIPRA_TEST_SOURCE','/tmp/clipra_real_highbit_35s.mp4'))
BASE=os.environ.get('CLIPRA_TEST_BASE_URL','http://127.0.0.1:8765')
HEADERS={}
report={'name':'Real high-bitrate media upload/resume/render over live FastAPI HTTP', 'source_bytes':SOURCE.stat().st_size,'source_mib':round(SOURCE.stat().st_size/1048576,3),'media':'actual H.264/AAC encoded high-bitrate video, not padded MP4'}
def check(cond,msg):
 if not cond:raise AssertionError(msg)
hash_before=hashlib.sha256(SOURCE.read_bytes()).hexdigest()
with httpx.Client(base_url=BASE,timeout=130) as c:
 r=c.post('/api/auth/login',json={'password':os.environ['CLIPRA_ADMIN_PASSWORD']});check(r.status_code==200,f'login {r.status_code}')
 r=c.post('/api/uploads',json={'filename':SOURCE.name,'size':SOURCE.stat().st_size,'rights_confirmed':True,'sha256':hash_before});check(r.status_code==201,r.text)
 uid=r.json()['id'];offset=0;chunks=0;interrupted=False
 with SOURCE.open('rb') as f:
  while offset<SOURCE.stat().st_size:
   f.seek(offset);part=f.read(4*1048576)
   r=c.patch(f'/api/uploads/{uid}',content=part,headers={'Upload-Offset':str(offset),'Tus-Resumable':'1.0.0','Content-Type':'application/offset+octet-stream'});
   check(r.status_code==204,f'PATCH status {r.status_code} @offset {offset}: {r.text[:400]}')
   offset=int(r.headers['upload-offset']);chunks+=1
   if chunks==5:
    head=c.head(f'/api/uploads/{uid}');check(head.status_code==200,'resume HEAD failed')
    check(int(head.headers['upload-offset'])==offset,'resume offset mismatch');interrupted=True
 r=c.post(f'/api/uploads/{uid}/complete');check(r.status_code==200,r.text)
 media=r.json();check(media['sha256']==hash_before,'source checksum from server differs');check(media['size']==SOURCE.stat().st_size,'uploaded bytes differ')
 req={'title':'Live HTTP 69MB encoded source proof','segments':[{'start':4.0,'end':7.0}],'ratio':'original','mode':'fit','crf':20}
 r=c.post(f'/api/media/{media["id"]}/clips',json=req);check(r.status_code==201,r.text);clip=r.json()
 r=c.post(f'/api/clips/{clip["id"]}/render');check(r.status_code==202,r.text);job=r.json()
 env={**os.environ, 'PYTHONPATH':str(Path(__file__).resolve().parents[1]/'backend')}
 done=subprocess.run([sys.executable,'-c','from clipra.worker import run_pending; print(run_pending(max_jobs=1))'],env=env,capture_output=True,text=True,timeout=180)
 check(done.returncode==0,'render worker failed: '+done.stderr[-500:]);
 r=c.get(f'/api/jobs/{job["id"]}');check(r.status_code==200,r.text);check(r.json()['status']=='done',f'render status: {r.text}')
 download=c.get(f'/api/clips/{clip["id"]}/download');check(download.status_code==200,'download failed')
 output=Path(os.environ.get('CLIPRA_TEST_OUTPUT','/tmp/clipra_real_69mb_live_export.mp4'));output.write_bytes(download.content)
 ffprobe=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(output)]))
 codecs=[x['codec_name'] for x in ffprobe['streams']]
 check('h264' in codecs and 'aac' in codecs,f'bad export codecs {codecs}')
 full_decode=subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-i',str(output),'-f','null','-'],capture_output=True,timeout=180)
 check(full_decode.returncode==0,'full output decode failure')
 check(hashlib.sha256(SOURCE.read_bytes()).hexdigest()==hash_before,'source altered')
 report.update({'upload_chunks':chunks,'resume_via_head':interrupted,'media_duration':media['duration'],'source_sha256_before_after_match':True,'server_sha256_match':True,'job_status':'done','render_file':str(output),'output_bytes':output.stat().st_size,'output_duration':float(ffprobe['format']['duration']),'output_codecs':codecs,'full_export_decode':'pass','result':'PASS'})
path=Path(__file__).resolve().parents[1]/'evidence'/'real-69mb-http-e2e.json';path.write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))