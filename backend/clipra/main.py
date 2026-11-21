import os
import re
import hmac
import fcntl
import hashlib
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse, parse_qs
from fastapi import FastAPI,Request,Response,HTTPException,Depends
from fastapi.responses import FileResponse,JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from itsdangerous import URLSafeTimedSerializer,BadSignature,SignatureExpired
from sqlalchemy import select
from .db import Session,init_db
from .models import Upload,Media,Job,Clip
from .media import verify_decodable,sha256_file,MediaError
from .render import validate_segments

ROOT=Path(os.getenv('MEDIA_ROOT','/tmp/clipra-next-media'))
MAX_UPLOAD=int(os.getenv('MAX_UPLOAD_BYTES',str(10*1024**3)))
MAX_CHUNK=8*1024*1024
app=FastAPI(title='CLIPRA AI NEXT',version='0.1.0',docs_url=None,redoc_url=None)

@app.on_event('startup')
def setup():
    password=os.getenv('CLIPRA_ADMIN_PASSWORD','')
    signing=os.getenv('CLIPRA_SESSION_SECRET','')
    if len(password)<16 or len(signing)<24 or 'REPLACE_' in password or 'REPLACE_' in signing:
        raise RuntimeError('Set unique strong CLIPRA_ADMIN_PASSWORD (16+ chars) and CLIPRA_SESSION_SECRET (24+ chars); refusing insecure defaults')
    init_db()
    for d in ('uploads','originals','exports'): (ROOT/d).mkdir(parents=True,exist_ok=True)

def signer():return URLSafeTimedSerializer(os.environ['CLIPRA_SESSION_SECRET'],salt='clipra-next-session')
def auth(req:Request):
    try:
        if signer().loads(req.cookies.get('clipra_session',''),max_age=7*24*3600)=='owner':return 'owner'
    except (BadSignature,SignatureExpired):pass
    raise HTTPException(401,'Login required')

def check_origin(req:Request):
    origin=req.headers.get('origin')
    if origin:
        own_host=req.headers.get('host','')
        forwarded_host=req.headers.get('x-forwarded-host','')
        approved={x.strip() for x in os.getenv('ALLOWED_ORIGINS','http://localhost:3000').split(',') if x.strip()}
        if urlparse(origin).netloc not in (own_host,forwarded_host) and origin not in approved:
            raise HTTPException(403,'Cross-site request blocked')

class Login(BaseModel): password:str
class UploadCreate(BaseModel):
    filename:str=Field(min_length=1,max_length=255)
    size:int=Field(gt=0)
    sha256:str|None=None
    rights_confirmed:bool
class SuggestRequest(BaseModel):
    max_clips:int=Field(default=4,ge=1,le=12)
    length_seconds:float=Field(default=22.0,ge=8.0,le=60.0)

class AnalyzeRequest(BaseModel):
    category:Literal['auto','gaming','podcast','livestream','education','drama','general']='auto'
    max_clips:int=Field(default=3,ge=1,le=12)
    consent:bool=False
class Segment(BaseModel):
    start:float=Field(ge=0)
    end:float=Field(gt=0)
class ClipRequest(BaseModel):
    title:str=Field(default='Selected highlight',min_length=1,max_length=180)
    segments:list[Segment]=Field(min_length=1,max_length=30)
    ratio:Literal['original','9:16','16:9','4:3','3:4','1:1']='original'
    mode:Literal['fit','fill']='fit'
    crf:int=Field(default=20,ge=16,le=28)
class YoutubeRequest(BaseModel):url:str=Field(max_length=2048)
class YoutubeLinkRequest(YoutubeRequest):rights_confirmed:bool

def clip_view(c:Clip):
    return {'id':c.id,'media_id':c.media_id,'title':c.title,'segments':c.segments,'duration':sum(x['end']-x['start'] for x in c.segments),
            'reasoning':c.reasoning,'origin':c.origin,'confidence':c.confidence,'options':c.options,
            'rendered':bool(c.output_path and Path(c.output_path).exists())}

def job_view(j:Job):
    return {'id':j.id,'kind':j.kind,'media_id':j.media_id,'clip_id':j.clip_id,'status':j.status,'stage':j.stage,'error':j.error,
            'settings':{k:v for k,v in (j.settings or {}).items() if k!='consent'}}

def get_media(s,id):
    m=s.get(Media,id)
    if not m:raise HTTPException(404,'Media not found')
    return m

def get_clip(s,id):
    c=s.get(Clip,id)
    if not c:raise HTTPException(404,'Clip not found')
    return c

@app.middleware('http')
async def security_headers(req:Request,call_next):
    resp=await call_next(req)
    resp.headers['X-Content-Type-Options']='nosniff'
    resp.headers['X-Frame-Options']='DENY'
    resp.headers['Referrer-Policy']='no-referrer'
    resp.headers['Cache-Control']='no-store'
    return resp

@app.get('/health')
def health():return {'status':'ok','service':'clipra-next-api'}
@app.get('/ready')
def ready():
    try:
        with Session() as s:s.execute(select(Upload.id).limit(1))
        return {'ready':True,'database':'ok'}
    except Exception:raise HTTPException(503,'Database unavailable')

@app.post('/api/auth/login')
def login(body:Login,response:Response,req:Request):
    check_origin(req)
    if not hmac.compare_digest(body.password,os.environ['CLIPRA_ADMIN_PASSWORD']):raise HTTPException(401,'Incorrect password')
    response.set_cookie('clipra_session',signer().dumps('owner'),max_age=7*24*3600,httponly=True,
       secure=os.getenv('COOKIE_SECURE','false')=='true',samesite='strict',path='/')
    return {'ok':True}
@app.post('/api/auth/logout')
def logout(response:Response,req:Request,user=Depends(auth)):
    check_origin(req);response.delete_cookie('clipra_session',path='/');return {'ok':True}
@app.get('/api/me')
def me(user=Depends(auth)):return {'user':'owner'}
@app.get('/api/providers')
def providers(user=Depends(auth)):
    return {'free_local':{'configured':True,'video_ai':False,'selection':'audio_visual_activity_drafts'},'gemini':{'configured':bool(os.getenv('GEMINI_API_KEY')),'outbound_enabled':os.getenv('ALLOW_EXTERNAL_AI')=='true',
            'model':os.getenv('GEMINI_VIDEO_MODEL','gemini-3.5-flash'),'video_verification':'not_verified_until_real_request'},
            'aggregate':{'configured':bool(os.getenv('AGGREGATOR_API_KEY')),'provider':os.getenv('AGGREGATOR_PROVIDER','unknown'),
             'video_verification':'not_implemented'},
            'youtube':{'configured':bool(os.getenv('YOUTUBE_API_KEY')),'media_delivery':'not_provided_by_data_api'}}

@app.post('/api/uploads',status_code=201)
def create_upload(body:UploadCreate,req:Request,user=Depends(auth)):
    check_origin(req)
    if not body.rights_confirmed:raise HTTPException(400,'Confirm your permission to process this media')
    if body.size>MAX_UPLOAD:raise HTTPException(413,'File exceeds server upload limit')
    allowed={'.mp4','.mov','.webm','.mkv','.m4v','.avi','.3gp'}
    if Path(body.filename).suffix.lower() not in allowed:
        raise HTTPException(415,'Unsupported source container; upload a regular video file')
    if body.sha256 and not re.fullmatch('[0-9a-fA-F]{64}',body.sha256):raise HTTPException(422,'Invalid SHA256')
    with Session() as s:
        up=Upload(filename=Path(body.filename).name,size=body.size,expected_sha256=body.sha256,rights_confirmed=True)
        s.add(up);s.commit()
        (ROOT/'uploads'/f'{up.id}.part').touch(exist_ok=False)
        return {'id':up.id,'offset':0,'max_chunk_bytes':MAX_CHUNK,'url':f'/api/uploads/{up.id}'}

@app.head('/api/uploads/{id}')
def head_upload(id:str,user=Depends(auth)):
    with Session() as s:
        up=s.get(Upload,id)
        if not up:raise HTTPException(404,'Upload not found')
        return Response(headers={'Upload-Offset':str(up.offset),'Upload-Length':str(up.size),'Tus-Resumable':'1.0.0'})

@app.patch('/api/uploads/{id}',status_code=204)
async def patch_upload(id:str,req:Request,user=Depends(auth)):
    check_origin(req)
    try:client_offset=int(req.headers['upload-offset'])
    except (KeyError,ValueError):raise HTTPException(400,'Upload-Offset header is required')
    clen=req.headers.get('content-length')
    if clen and int(clen)>MAX_CHUNK:raise HTTPException(413,'Chunk exceeds 8 MiB')
    path=ROOT/'uploads'/f'{id}.part'
    with Session() as s:
        up=s.get(Upload,id)
        if not up or up.status!='uploading':raise HTTPException(404,'Upload not active')
        if not path.exists():raise HTTPException(409,'Partial upload file missing')
        lock=ROOT/'uploads'/f'{id}.lock'
        with lock.open('a+b') as lf:
            fcntl.flock(lf.fileno(),fcntl.LOCK_EX)
            with path.open('r+b') as f:
                f.seek(0,2);actual=f.tell()
                if actual!=up.offset:up.offset=actual;s.commit()
                if actual!=client_offset:raise HTTPException(409, f'Expected upload offset {actual}')
                count=0
                try:
                    async for chunk in req.stream():
                        count+=len(chunk)
                        if count>MAX_CHUNK or actual+count>up.size:raise HTTPException(413,'Upload length exceeded')
                        f.write(chunk)
                    f.flush();os.fsync(f.fileno())
                finally:
                    # A disconnected client may have transferred part of a chunk; report the real durable offset on resume.
                    f.seek(0,2);up.offset=f.tell();s.commit()
            return Response(status_code=204,headers={'Upload-Offset':str(up.offset),'Tus-Resumable':'1.0.0'})

@app.post('/api/uploads/{id}/complete')
def complete_upload(id:str,req:Request,user=Depends(auth)):
    check_origin(req)
    with Session() as s:
        up=s.get(Upload,id)
        if not up or up.status!='uploading':raise HTTPException(404,'Upload not active')
        path=ROOT/'uploads'/f'{id}.part'
        if not path.exists() or path.stat().st_size!=up.size:raise HTTPException(409,'Upload incomplete')
        checksum=sha256_file(path)
        if up.expected_sha256 and checksum.lower()!=up.expected_sha256.lower():raise HTTPException(422,'Checksum mismatch')
        try:meta=verify_decodable(path)
        except MediaError as e:raise HTTPException(415,str(e))
        if any(x in meta['format'] for x in ('hls','concat','dash','image2')):
            raise HTTPException(415,'Playlists and indirect media sources are not supported')
        source=ROOT/'originals'/f'{id}.media'
        os.replace(path,source)
        m=Media(filename=up.filename,source_path=str(source),sha256=checksum,size=up.size,**{k:meta[k] for k in ('duration','width','height','fps','has_audio')})
        s.add(m);up.status='completed';s.commit()
        return {'id':m.id,'filename':m.filename,'sha256':m.sha256,'size':m.size,'duration':m.duration,
                'width':m.width,'height':m.height,'fps':m.fps,'has_audio':m.has_audio,'youtube_url':m.youtube_url}

@app.get('/api/media')
def list_media(user=Depends(auth)):
    with Session() as s:
        return [{'id':m.id,'filename':m.filename,'duration':m.duration,'width':m.width,'height':m.height,'size':m.size}
                for m in s.scalars(select(Media).where(Media.duration>0).order_by(Media.created_at.desc()).limit(50))]
@app.get('/api/media/{id}')
def media_details(id:str,user=Depends(auth)):
    with Session() as s:
        m=get_media(s,id)
        return {'id':m.id,'filename':m.filename,'size':m.size,'sha256':m.sha256,'duration':m.duration,
                'width':m.width,'height':m.height,'fps':m.fps,'has_audio':m.has_audio,'youtube_url':m.youtube_url}
@app.get('/api/media/{id}/stream')
def stream_media(id:str,user=Depends(auth)):
    with Session() as s:
        m=get_media(s,id)
        mt={'.mov':'video/quicktime','.webm':'video/webm','.mkv':'video/x-matroska','.avi':'video/x-msvideo'}.get(Path(m.filename).suffix.lower(),'video/mp4')
        return FileResponse(m.source_path,media_type=mt,filename=m.filename,content_disposition_type='inline')

@app.post('/api/media/{id}/suggest',status_code=202)
def suggest_free_clips(id:str,body:SuggestRequest,req:Request,user=Depends(auth)):
    """Queue free on-server audio/visual drafts. Never bills AI tokens."""
    check_origin(req)
    with Session() as s:
        m=get_media(s,id)
        if m.duration<=0 or not Path(m.source_path).exists():
            raise HTTPException(409,'Original source is not available')
        active=s.scalar(select(Job).where(Job.media_id==id,Job.kind=='suggest',
                       Job.status.in_(['queued','running'])).limit(1))
        if active:return job_view(active)
        j=Job(kind='suggest',media_id=id,settings={
            'max_clips':body.max_clips,'clip_length':body.length_seconds,
            'selection':'local_audiovisual_drafts_not_semantic_ai'})
        s.add(j);s.commit()
        return job_view(j)

@app.post('/api/media/{id}/analyze',status_code=202)
def analyze(id:str,body:AnalyzeRequest,req:Request,user=Depends(auth)):
    check_origin(req)
    if not body.consent:raise HTTPException(400,'Explicit external AI analysis consent required')
    with Session() as s:
        m=get_media(s,id)
        existing=s.scalar(select(Job).where(Job.media_id==id,Job.kind=='analyze',Job.status.in_(['queued','running'])).limit(1))
        if existing:return job_view(existing)
        j=Job(kind='analyze',media_id=m.id,settings={'consent':body.consent,'category':body.category if body.category!='auto' else 'general','max_clips':body.max_clips})
        s.add(j);s.commit();return job_view(j)

@app.post('/api/media/{id}/clips',status_code=201)
def create_clip(id:str,body:ClipRequest,req:Request,user=Depends(auth)):
    check_origin(req)
    with Session() as s:
        m=get_media(s,id);segments=[p.model_dump() for p in body.segments]
        try:validate_segments(segments,m.duration)
        except ValueError as e:raise HTTPException(422,str(e))
        c=Clip(media_id=id,title=body.title,segments=segments,origin='manual',
               options={'ratio':body.ratio,'mode':body.mode,'crf':body.crf})
        s.add(c);s.commit();return clip_view(c)
@app.get('/api/media/{id}/clips')
def clips(id:str,user=Depends(auth)):
    with Session() as s:
        get_media(s,id)
        return [clip_view(c) for c in s.scalars(select(Clip).where(Clip.media_id==id).order_by(Clip.created_at))]
@app.put('/api/clips/{id}')
def update_clip(id:str,body:ClipRequest,req:Request,user=Depends(auth)):
    check_origin(req)
    with Session() as s:
        c=get_clip(s,id);m=get_media(s,c.media_id);segments=[p.model_dump() for p in body.segments]
        # Editing a clip while its worker is encoding would race with the old
        # segments and publish a stale result under the updated edit decision list.
        active=s.scalar(select(Job.id).where(Job.clip_id==id, Job.kind=='render',
            Job.status.in_(['queued','running'])).limit(1))
        if active:
            raise HTTPException(409,'A render is queued or running; cancel or finish it before editing this clip')
        try:validate_segments(segments,m.duration)
        except ValueError as e:raise HTTPException(422,str(e))
        if c.output_path and Path(c.output_path).exists():Path(c.output_path).unlink()
        c.title=body.title;c.segments=segments;c.output_path=None;c.options={'ratio':body.ratio,'mode':body.mode,'crf':body.crf}
        s.commit();return clip_view(c)
@app.post('/api/clips/{id}/render',status_code=202)
def request_render(id:str,req:Request,user=Depends(auth)):
    check_origin(req)
    with Session() as s:
        c=get_clip(s,id)
        existing=s.scalar(select(Job).where(Job.clip_id==id,Job.status.in_(['queued','running'])).limit(1))
        if existing:return job_view(existing)
        j=Job(kind='render',media_id=c.media_id,clip_id=c.id)
        s.add(j);s.commit();return job_view(j)
@app.get('/api/clips/{id}/download')
def download(id:str,user=Depends(auth)):
    with Session() as s:
        c=get_clip(s,id)
        if not c.output_path or not Path(c.output_path).exists():raise HTTPException(409,'Clip has not been rendered')
        return FileResponse(c.output_path,filename=f'clipra-{id[:8]}.mp4',media_type='video/mp4')
@app.get('/api/clips/{id}/preview')
def preview(id:str,user=Depends(auth)):
    with Session() as s:
        c=get_clip(s,id)
        if not c.output_path or not Path(c.output_path).exists():raise HTTPException(409,'Clip has not been rendered')
        return FileResponse(c.output_path,media_type='video/mp4',content_disposition_type='inline')
@app.get('/api/jobs/{id}')
def job_status(id:str,user=Depends(auth)):
    with Session() as s:
        j=s.get(Job,id)
        if not j:raise HTTPException(404,'Job not found')
        return job_view(j)
@app.post('/api/jobs/{id}/cancel')
def cancel(id:str,req:Request,user=Depends(auth)):
    check_origin(req)
    with Session() as s:
        j=s.get(Job,id)
        if not j:raise HTTPException(404,'Job not found')
        j.cancelled=True
        if j.status=='queued':j.status='cancelled'
        elif j.status=='running':j.stage='cancellation requested'
        s.commit();return job_view(j)
@app.post('/api/jobs/{id}/retry')
def retry(id:str,req:Request,user=Depends(auth)):
    check_origin(req)
    with Session() as s:
        j=s.get(Job,id)
        if not j:raise HTTPException(404,'Job not found')
        if j.status not in ('failed','blocked'):raise HTTPException(409,'Only failed/blocked jobs may be retried')
        j.status='queued';j.stage='queued';j.error=None;j.cancelled=False;s.commit();return job_view(j)

def youtube_reference(url:str)->tuple[str,str]:
    parsed=urlparse(url)
    if parsed.scheme!='https' or parsed.hostname not in ('youtube.com','www.youtube.com','m.youtube.com','youtu.be'):
        raise HTTPException(422,'A valid HTTPS YouTube URL is required')
    video_id=(parsed.path.strip('/') if parsed.hostname=='youtu.be' else
              parse_qs(parsed.query).get('v',[''])[0] if parsed.path=='/watch' else
              parsed.path.strip('/').split('/')[-1] if parsed.path.startswith(('/shorts/','/live/')) else '')
    if not re.fullmatch('[a-zA-Z0-9_-]{11}',video_id):raise HTTPException(422,'Invalid YouTube video reference')
    return video_id,f'https://www.youtube.com/watch?v={video_id}'

@app.post('/api/youtube/inspect')
def youtube(body:YoutubeRequest,req:Request,user=Depends(auth)):
    check_origin(req)
    video_id,canonical=youtube_reference(body.url)
    return {'video_id':video_id,'reference':canonical,
            'status':'requires_authorized_original','media_bytes_available':False,
            'ai_url_understanding':'documented_preview_provider_capability_not_verified_on_this_account',
            'message':'Google documents YouTube URL video understanding, but it does not supply MP4 source bytes. Attach a creator-owned original to export actual clips.'}

@app.post('/api/youtube/import',status_code=202)
def import_authorized_youtube(body:YoutubeLinkRequest,req:Request,user=Depends(auth)):
    check_origin(req)
    if not body.rights_confirmed:
        raise HTTPException(400,'Confirm you own or can process this YouTube recording')
    video_id,canonical=youtube_reference(body.url)
    with Session() as s:
        active=s.scalar(select(Job).where(Job.kind=='youtube_import',
                      Job.status.in_(['queued','running'])).limit(1))
        if active:
            raise HTTPException(409,'A YouTube import is already in progress')
        # New media is deliberately hidden from the library until validated.
        media=Media(filename=f'YouTube {video_id} (importing)',source_path='',
                    sha256='',size=0,duration=0,width=0,height=0,fps=0,
                    has_audio=False,youtube_url=canonical)
        s.add(media);s.flush()
        j=Job(kind='youtube_import',media_id=media.id,settings={
            'video_id':video_id,'rights_confirmed':True,
            'source':'public_youtube_or_bounded_live'})
        s.add(j);s.commit()
        return job_view(j)

@app.post('/api/media/{id}/youtube')
def associate_youtube(id:str,body:YoutubeLinkRequest,req:Request,user=Depends(auth)):
    check_origin(req)
    if not body.rights_confirmed:raise HTTPException(400,'Confirm this is the authorized original recording for this YouTube reference')
    video_id,canonical=youtube_reference(body.url)
    with Session() as s:
        m=get_media(s,id)
        m.youtube_url=canonical
        s.commit()
        return {'media_id':m.id,'youtube_url':m.youtube_url,'video_id':video_id,
            'media_bytes_available':True,'source':'owner_supplied_original',
            'identity_verification':'owner_attestation_only_not_provider_verified'}

# A dependency-free first-party website served by this API, alongside the Next.js source.
# The UI is not an external mock: every action calls the same authenticated backend.
SITE=Path(__file__).resolve().parent/'site'
app.mount('/studio-assets',StaticFiles(directory=str(SITE)),name='studio-assets')
@app.get('/',include_in_schema=False)
def home():
    return FileResponse(SITE/'index.html',media_type='text/html')