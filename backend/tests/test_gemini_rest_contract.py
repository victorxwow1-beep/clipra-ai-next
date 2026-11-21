"""Real HTTP wire-format contract against a simulated Google endpoint.

These tests DO NOT establish that Gemini analyzed a real video: there is no
external credential. They show our client posts actual MP4 bytes to the provider
route and parses response/cost data using the official documented protocol.
"""
import json, httpx, pytest
from clipra.gemini_rest import GeminiVideoREST, GeminiProviderError


def test_google_file_api_upload_uses_actual_bytes_and_structured_response(source):
    calls=[]
    uri='https://generativelanguage.googleapis.com/v1beta/files/test001'
    def handler(request):
        calls.append((request.method,str(request.url),len(request.content)))
        assert request.headers['x-goog-api-key']=='TEST_CREDENTIAL_NOT_REAL'
        if request.method=='GET' and '/models/' in request.url.path:
            return httpx.Response(200,json={'name':'models/gemini-3.5-flash'})
        if request.url.path=='/upload/v1beta/files' and request.headers.get('x-goog-upload-command')=='start':
            return httpx.Response(200,headers={'x-goog-upload-url':uri})
        if request.url.path=='/v1beta/files/test001' and request.headers.get('x-goog-upload-command')=='upload, finalize':
            assert request.content==source.read_bytes()
            assert b'ftyp' in request.content[:100]
            return httpx.Response(200,json={'file':{'name':'files/test001','uri':uri,'state':'ACTIVE'}})
        if request.url.path.endswith(':generateContent'):
            payload=json.loads(request.content)
            assert payload['contents'][0]['parts'][0]['file_data']['file_uri']==uri
            assert payload['generationConfig']['responseMimeType']=='application/json'
            return httpx.Response(200,json={'candidates':[{'content':{'parts':[{'text':json.dumps({'moments':[]})}]}}],
                'usageMetadata':{'promptTokenCount':101,'candidatesTokenCount':5}})
        if request.method=='DELETE' and request.url.path=='/v1beta/files/test001':
            return httpx.Response(200,json={})
        raise AssertionError(f'Unexpected Google API call {request.method} {request.url}')
    with GeminiVideoREST('TEST_CREDENTIAL_NOT_REAL','gemini-3.5-flash',transport=httpx.MockTransport(handler)) as api:
        api.model_metadata()
        name,file_uri=api.upload_video(source)
        content,usage=api.infer(file_uri,'Describe actual scenes',{'type':'object','properties':{'moments':{'type':'array'}}})
        api.delete_file(name)
    assert json.loads(content)=={'moments':[]}
    assert usage['promptTokenCount']==101
    assert len(calls)==5


def test_untrusted_provider_upload_url_rejected_before_media_transfer(source):
    def handler(request):
        return httpx.Response(200,headers={'x-goog-upload-url':'https://attacker.invalid/steal'})
    with GeminiVideoREST('TEST_CREDENTIAL_NOT_REAL','gemini-3.5-flash',transport=httpx.MockTransport(handler)) as api:
        with pytest.raises(GeminiProviderError,match='trusted-host'):
            api.upload_video(source)


def test_failed_gemini_activation_deletes_uploaded_media(source):
    calls=[]
    uri='https://generativelanguage.googleapis.com/v1beta/files/expired'
    def handler(request):
        calls.append((request.method,request.url.path))
        if request.url.path=='/upload/v1beta/files':
            return httpx.Response(200,headers={'x-goog-upload-url':uri})
        if request.method=='POST' and request.url.path=='/v1beta/files/expired':
            return httpx.Response(200,json={'file':{'name':'files/expired','uri':uri,'state':'FAILED'}})
        if request.method=='DELETE' and request.url.path=='/v1beta/files/expired':
            return httpx.Response(200,json={})
        raise AssertionError('Unexpected request')
    with GeminiVideoREST('TEST_CREDENTIAL_NOT_REAL','gemini-3.5-flash',transport=httpx.MockTransport(handler)) as api:
        with pytest.raises(GeminiProviderError,match='rejected processing'):
            api.upload_video(source)
    assert ('DELETE','/v1beta/files/expired') in calls


@pytest.mark.parametrize('url',[
    'https://user:pass@generativelanguage.googleapis.com/upload/v1beta/files',
    'https://generativelanguage.googleapis.com:8443/upload/v1beta/files',
    'http://generativelanguage.googleapis.com/upload/v1beta/files',
    'https://generativelanguage.googleapis.com.evil.invalid/upload/v1beta/files',
])
def test_untrusted_google_upload_redirects_rejected(source,url):
    def handler(request):
        return httpx.Response(200,headers={'x-goog-upload-url':url})
    with GeminiVideoREST('TEST_CREDENTIAL_NOT_REAL','gemini-3.5-flash',transport=httpx.MockTransport(handler)) as api:
        with pytest.raises(GeminiProviderError,match='trusted-host'):
            api.upload_video(source)