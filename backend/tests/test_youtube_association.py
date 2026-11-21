from .conftest import upload_file
from clipra.worker import run_pending

def test_youtube_reference_linked_only_to_authorized_original(client,source):
    media=upload_file(client,source)
    path=f'/api/media/{media["id"]}/youtube'
    bad=client.post(path,json={'url':'https://youtu.be/dQw4w9WgXcQ','rights_confirmed':False})
    assert bad.status_code==400
    linked=client.post(path,json={'url':'https://youtu.be/dQw4w9WgXcQ','rights_confirmed':True})
    assert linked.status_code==200,linked.text
    assert linked.json()['source']=='owner_supplied_original'
    assert linked.json()['identity_verification']=='owner_attestation_only_not_provider_verified'
    assert client.get(f'/api/media/{media["id"]}').json()['youtube_url']=='https://www.youtube.com/watch?v=dQw4w9WgXcQ'
    assert client.post(path,json={'url':'https://malicious.invalid','rights_confirmed':True}).status_code==422
    # Real render still comes from original bytes, NEVER from YouTube metadata.
    clip=client.post(f'/api/media/{media["id"]}/clips',json={
        'title':'Authorized original clip','segments':[{'start':0.5,'end':2.2}]}).json()
    job=client.post(f'/api/clips/{clip["id"]}/render').json()
    assert run_pending(max_jobs=1)==1
    assert client.get(f'/api/jobs/{job["id"]}').json()['status']=='done'
    assert len(client.get(f'/api/clips/{clip["id"]}/download').content)>1000