"""Acceptance tests for edit/render lifecycle; failures used to silently show stale output."""
from clipra.models import Job, Clip
from clipra.db import Session
from clipra.worker import run_one
from .conftest import upload_file


def test_cannot_edit_clip_while_render_queued(client, source):
    media=upload_file(client,source)
    original={'title':'first edit', 'segments':[{'start':1,'end':3}], 'ratio':'original'}
    clip=client.post(f'/api/media/{media["id"]}/clips',json=original).json()
    request=client.post(f'/api/clips/{clip["id"]}/render')
    assert request.status_code==202
    changed={'title':'second edit', 'segments':[{'start':7,'end':10}], 'ratio':'original'}
    conflict=client.put(f'/api/clips/{clip["id"]}',json=changed)
    assert conflict.status_code==409
    assert 'render' in conflict.json()['detail']
    assert client.post(f'/api/jobs/{request.json()["id"]}/cancel').json()['status']=='cancelled'
    accepted=client.put(f'/api/clips/{clip["id"]}',json=changed)
    assert accepted.status_code==200
    assert accepted.json()['segments']==changed['segments']


def test_worker_late_cancellation_does_not_leave_export(client, source, monkeypatch):
    """User cancellation between encode completion and status commit must clean output."""
    from clipra import worker
    media=upload_file(client,source)
    clip=client.post(f'/api/media/{media["id"]}/clips',json={'segments':[{'start':1,'end':3}]}).json()
    job=client.post(f'/api/clips/{clip["id"]}/render').json()
    original_render=worker.render_clip

    def render_then_cancel(*args, **kwargs):
        result=original_render(*args,**kwargs)
        # This models a concurrent cancellation after FFmpeg publishes the file.
        with Session() as session:
            dbjob=session.get(Job,job['id'])
            dbjob.cancelled=True
            session.commit()
        return result

    monkeypatch.setattr(worker,'render_clip',render_then_cancel)
    with Session() as session:
        dbjob=session.get(Job,job['id'])
        dbjob.status='running'
        session.commit()
    run_one(job['id'])
    assert client.get(f'/api/jobs/{job["id"]}').json()['status']=='cancelled'
    assert client.get(f'/api/clips/{clip["id"]}/download').status_code==409
    with Session() as session:
        saved=session.get(Clip,clip['id'])
        assert saved.output_path is None