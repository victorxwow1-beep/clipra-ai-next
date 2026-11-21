"""Durable, independent FFmpeg worker. In production run a dedicated process per instance.

Postgres SELECT FOR UPDATE SKIP LOCKED avoids multiple workers taking the same job.
"""
import os
import time
import traceback
from datetime import datetime,timezone,timedelta
from pathlib import Path
from sqlalchemy import select,update,or_
from .db import Session, init_db
from .models import Job,Media,Clip
from .ai import analyze_video, AIUnavailable
from .signals import discover_signals
from .freecuts import propose_drafts
from .semantic_evidence import analyze_hud_video
from .local_speech import transcribe_local, LocalSpeechUnavailable
from .youtube_source import download_authorized_youtube, YouTubeImportError
from .render import render_clip,RenderCancelled

ROOT=Path(os.getenv('MEDIA_ROOT','/tmp/clipra-next-media'))

def run_one(job_id):
    with Session() as s:
        job=s.get(Job,job_id)
        if not job or job.status!='running':return
        if job.cancelled:
            job.status='cancelled';s.commit();return
        media=s.get(Media,job.media_id)
        clip=s.get(Clip,job.clip_id) if job.clip_id else None
        job.stage={'analyze':'analyzing audiovisual content','suggest':'scanning original locally','evidence':'checking actual source frames for on-screen event evidence','smart':'analyzing real source evidence (no paid API)','youtube_import':'importing authorized YouTube source','render':'encoding original video'}.get(job.kind,'starting')
        job.heartbeat=datetime.now(timezone.utc);s.commit()
        try:
            if job.kind=='analyze':
                settings=job.settings or {}
                if not settings.get('consent'):raise AIUnavailable('External media analysis consent missing')
                found,usage=analyze_video(Path(media.source_path),media.duration,settings.get('category','general'),settings.get('max_clips',3))
                for m in found:
                    c=Clip(media_id=media.id,title=m['title'],segments=[{'start':m['start'],'end':m['end']}],
                           origin='gemini_ai',reasoning=m['reason']+' | Evidence: '+str(m['evidence']),confidence=m['confidence'])
                    s.add(c)
                job.settings={**settings,'usage':usage,'candidate_count':len(found)}
            elif job.kind=='suggest':
                settings=job.settings or {}
                suggestions=propose_drafts(
                    media.duration,
                    discover_signals(Path(media.source_path), media.duration, max_events=64),
                    max_clips=int(settings.get('max_clips',4)),
                    clip_length=float(settings.get('clip_length',22.0)),
                )
                for moment in suggestions:
                    s.add(Clip(
                        media_id=media.id, title=moment['title'],
                        segments=[{'start':moment['start'],'end':moment['end']}],
                        origin='signal_draft', confidence=None,
                        reasoning=moment['reason'],
                        options={'ratio':'9:16','mode':'fit','crf':20},
                    ))
                job.settings={**settings,'candidate_count':len(suggestions),'selection':'local_audiovisual_drafts_not_semantic_ai'}
            elif job.kind=='evidence':
                settings=job.settings or {}
                if media.duration > float(os.getenv("MAX_LOCAL_EVIDENCE_SECONDS","3600")):
                    raise ValueError("Source exceeds the 60-minute free evidence scan limit. Split it before analysis.")
                cues=discover_signals(Path(media.source_path),media.duration,max_events=64)
                findings,summary=analyze_hud_video(
                    Path(media.source_path),media.duration,cues,
                    max_clips=int(settings.get("max_clips",4)),
                    clip_length=float(settings.get("clip_length",22)),
                    max_frames=int(os.getenv("MAX_LOCAL_EVIDENCE_FRAMES","45")))
                for item in findings:
                    s.add(Clip(
                        media_id=media.id,title=item["title"],
                        segments=[{"start":item["start"],"end":item["end"]}],
                        origin="local_text_evidence",reasoning=item["reason"],
                        confidence=None,
                        options={"ratio":"9:16","mode":"fit","crf":18}))
                job.settings={**settings,"candidate_count":len(findings),"evidence":summary,
                              "selection":"visible_hud_text_not_full_event_recognition"}
            elif job.kind=='smart':
                settings=job.settings or {}
                category=settings.get('category','auto')
                max_clips=int(settings.get('max_clips',5))
                clip_length=float(settings.get('clip_length',24))
                source=Path(media.source_path)
                if not source.is_file():
                    raise ValueError('Original source missing; please upload again')
                found=[]
                analyses=[]
                if category in ('gaming','auto','livestream'):
                    if media.duration>float(os.getenv('MAX_LOCAL_EVIDENCE_SECONDS','3600')):
                        raise LocalSpeechUnavailable('Free gameplay scan supports up to 60 minutes currently; no unverified highlights were produced')
                    cues=discover_signals(source, media.duration,max_events=64)
                    ocr,details=analyze_hud_video(source,media.duration,cues,
                                max_clips=max_clips,clip_length=min(60,clip_length),
                                max_frames=int(os.getenv('MAX_LOCAL_EVIDENCE_FRAMES','45')))
                    found.extend(ocr);analyses.append(details)
                # Spoken content requires actual local speech recognition (MIT-licensed
                # faster-whisper). It is not fabricated from motion or screen text.
                if category in ('podcast','education','livestream') or (category=='auto' and not found):
                    speech,details=transcribe_local(source,media.duration,max_clips=max_clips,
                                             clip_length=clip_length,category=category)
                    found.extend(speech);analyses.append(details)
                if category=='funny':
                    raise LocalSpeechUnavailable(
                        'Reliable funny-moment recognition needs a configured video-capable open-source vision model. '
                        'This server has no verified model runtime; refusing to invent highlights.')
                accepted=[]
                for item in found:
                    if any(max(0,min(item['end'],p['end'])-max(item['start'],p['start']))
                           > .4*min(item['end']-item['start'],p['end']-p['start'])
                           for p in accepted):
                        continue
                    accepted.append(item)
                    if len(accepted)>=max_clips:break
                for item in accepted:
                    s.add(Clip(
                        media_id=media.id,title=item['title'],
                        segments=[{'start':item['start'],'end':item['end']}],
                        origin=item['origin'],confidence=None,
                        reasoning=item['reason'],
                        options={
                            'ratio':settings.get('ratio','9:16'),
                            'mode':settings.get('mode','fit'),
                            'crf':int(settings.get('crf',18))}))
                job.settings={**settings,'candidate_count':len(accepted),
                    'analyses':analyses,'analysis_scope':'verified_visible_HUD_or_real_speech_only',
                    'multimodal_vision_model':'not_configured',
                    'note':'Clip quality requires human review; no fake semantic certainty.'}
            elif job.kind=='youtube_import':
                settings=job.settings or {}
                if not settings.get('rights_confirmed'):
                    raise YouTubeImportError('Rights confirmation required before YouTube import')
                result=download_authorized_youtube(settings['video_id'], ROOT)
                media.source_path=str(result['path'])
                media.filename=result['filename']
                media.sha256=result['sha256']
                media.size=result['size']
                media.duration=result['duration']
                media.width=result['width']
                media.height=result['height']
                media.fps=result['fps']
                media.has_audio=result['has_audio']
                media.youtube_url=result['youtube_url']
                job.settings={**settings,'source_status':result['source_status']}
            elif job.kind=='render':
                if not clip:raise ValueError('Clip not found')
                out=ROOT/'exports'/f'{clip.id}.mp4'
                options=clip.options or {}
                def is_cancelled():
                    with Session() as poll:
                        row=poll.get(Job,job_id)
                        return bool(row.cancelled) if row else True
                render_clip(Path(media.source_path),out,clip.segments,crf=int(options.get('crf',20)),
                           ratio=options.get('ratio','original'),mode=options.get('mode','fit'),should_cancel=is_cancelled)
                clip.output_path=str(out)
            else:raise ValueError('Unknown job kind')
            s.refresh(job, attribute_names=['cancelled'])
            if job.cancelled:
                # A cancellation arriving after FFmpeg has atomically published
                # its output must not leave a cancelled job with a downloadable
                # or disk-resident file which looks like an approved result.
                if job.kind=='render' and clip:
                    if clip.output_path:
                        Path(clip.output_path).unlink(missing_ok=True)
                    clip.output_path=None
                job.status='cancelled'
            else:
                job.status='done'
            job.stage='complete' if job.status=='done' else 'cancelled'
            s.commit()
        except RenderCancelled as e:
            s.rollback()
            job=s.get(Job,job_id);job.status='cancelled';job.stage='cancelled';job.error=None;s.commit()
        except Exception as e:
            s.rollback()
            job=s.get(Job,job_id)
            job.status='blocked' if isinstance(e,(AIUnavailable,YouTubeImportError,LocalSpeechUnavailable)) else 'failed'
            job.error=str(e)[:1000]
            job.stage='blocked' if job.status=='blocked' else 'failed'
            s.commit()

def claim_next():
    with Session() as s:
        q=select(Job).where(Job.status=='queued').order_by(Job.created_at).limit(1)
        if s.bind.dialect.name=='postgresql':q=q.with_for_update(skip_locked=True)
        job=s.scalar(q)
        if not job:return None
        if job.cancelled:job.status='cancelled';s.commit();return None
        job.status='running';job.stage='starting';job.heartbeat=datetime.now(timezone.utc);jid=job.id;s.commit();return jid

def run_pending(max_jobs=1):
    count=0
    while count<max_jobs:
        jid=claim_next()
        if not jid:break
        run_one(jid);count+=1
    return count

def recover_stalled(seconds=900):
    cutoff=datetime.now(timezone.utc)-timedelta(seconds=seconds)
    with Session() as s:
        for j in s.scalars(select(Job).where(Job.status=='running')):
            hb=j.heartbeat
            if hb and hb.tzinfo is None:hb=hb.replace(tzinfo=timezone.utc)
            if hb is None or hb<cutoff:j.status='failed';j.error='Worker halted during processing; manually retry using the original source'
        s.commit()

if __name__=='__main__':
    init_db();ROOT.mkdir(parents=True,exist_ok=True)
    recover_stalled()
    while True:
        if not run_pending():time.sleep(2)