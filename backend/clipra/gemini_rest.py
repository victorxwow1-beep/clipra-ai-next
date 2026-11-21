"""Google Gemini Files API + multimodal generateContent REST adapter.

Uses real uploaded MP4 bytes, server-held API key and Google endpoints only.
Does not send media without caller consent (enforced in API/worker).
Isolates provider errors, so API keys and media are never included in logs.
Ref: https://ai.google.dev/api/files
"""
from __future__ import annotations
import re
import time
from pathlib import Path
from urllib.parse import urlparse
import httpx

BASE='https://generativelanguage.googleapis.com'

class GeminiProviderError(RuntimeError):pass

class GeminiVideoREST:
    def __init__(self,api_key:str,model:str,*,transport=None):
        if not api_key:raise GeminiProviderError('Gemini API credential missing')
        if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{1,100}',model):
            raise GeminiProviderError('Gemini model identifier invalid')
        self.model=model
        self.client=httpx.Client(transport=transport,timeout=90,follow_redirects=False,
            headers={'x-goog-api-key':api_key})

    def __enter__(self):return self
    def __exit__(self,*args):self.client.close()

    def _check(self,response:httpx.Response,stage:str):
        if response.status_code>=400:
            # Never echo body: provider errors sometimes contain request secrets.
            if response.status_code in (401,403):
                raise GeminiProviderError(f'Gemini {stage}: API credential or permissions denied (HTTP {response.status_code})')
            if response.status_code==429:
                raise GeminiProviderError('Gemini quota or rate limit reached (HTTP 429)')
            raise GeminiProviderError(f'Gemini {stage} failed (HTTP {response.status_code})')
        try:return response.json()
        except ValueError as e:raise GeminiProviderError(f'Gemini {stage} response is not JSON') from e

    def model_metadata(self):
        return self._check(self.client.get(f'{BASE}/v1beta/models/{self.model}'), 'model lookup')

    def upload_video(self,file:Path):
        file=Path(file);count=file.stat().st_size
        if count<1:raise GeminiProviderError('Video proxy is empty')
        start=self.client.post(f'{BASE}/upload/v1beta/files',headers={
            'X-Goog-Upload-Protocol':'resumable',
            'X-Goog-Upload-Command':'start',
            'X-Goog-Upload-Header-Content-Length':str(count),
            'X-Goog-Upload-Header-Content-Type':'video/mp4',
            'Content-Type':'application/json'},json={'file':{'display_name':'clipra-analysis-window'}})
        if start.status_code>=400:self._check(start,'upload start')  # Start normally has header-only response
        upload_url=start.headers.get('x-goog-upload-url','')
        parsed=urlparse(upload_url)
        try:port=parsed.port
        except ValueError:port=None
        if (parsed.scheme!='https' or parsed.hostname!='generativelanguage.googleapis.com'
            or parsed.username is not None or parsed.password is not None
            or port not in (None,443) or not upload_url.startswith(f'{BASE}/')):
            raise GeminiProviderError('Gemini upload destination did not pass the trusted-host check')
        with file.open('rb') as f:
            response=self.client.post(upload_url,headers={
                'X-Goog-Upload-Offset':'0',
                'X-Goog-Upload-Command':'upload, finalize',
                'Content-Length':str(count),'Content-Type':'video/mp4'},content=f,timeout=240)
        document=self._check(response,'video file upload')
        obj=document.get('file') or {}
        name=obj.get('name','')
        if not re.fullmatch(r'files/[A-Za-z0-9_-]+',name):
            raise GeminiProviderError('Gemini did not return a valid file name')
        # Once the provider has allocated a file, delete it even if polling
        # fails, returns FAILED, times out, or the activation response is bad.
        try:
            deadline=time.monotonic()+240
            while obj.get('state')=='PROCESSING' or not obj.get('state'):
                if time.monotonic()>deadline:raise GeminiProviderError('Gemini video file activation timed out')
                time.sleep(3)
                obj=self._check(self.client.get(f'{BASE}/v1beta/{name}'),'file processing')
            if obj.get('state')!='ACTIVE':raise GeminiProviderError('Gemini video file rejected processing')
            uri=obj.get('uri','')
            if not isinstance(uri,str) or not uri.startswith('https://'):
                raise GeminiProviderError('Gemini video file URI missing')
            return name,uri
        except Exception:
            self.delete_file(name)
            raise

    def infer(self,uri:str,prompt:str,schema:dict):
        body={'contents':[{'role':'user','parts':[
            {'file_data':{'mime_type':'video/mp4','file_uri':uri}}, {'text':prompt}
        ]}], 'generationConfig':{
            'temperature':0.1,'responseMimeType':'application/json','responseSchema':schema,
        }}
        response=self._check(self.client.post(f'{BASE}/v1beta/models/{self.model}:generateContent',json=body,timeout=180),'video analysis')
        candidates=response.get('candidates') or []
        if not candidates:raise GeminiProviderError('Gemini returned no video analysis candidate')
        texts=[p.get('text','') for p in candidates[0].get('content',{}).get('parts',[]) if p.get('text')]
        if not texts:raise GeminiProviderError('Gemini returned no textual model evidence')
        return ''.join(texts),response.get('usageMetadata') or {}

    def delete_file(self,name):
        if re.fullmatch(r'files/[A-Za-z0-9_-]+',str(name)):
            try:self.client.delete(f'{BASE}/v1beta/{name}',timeout=30)
            except httpx.HTTPError:pass