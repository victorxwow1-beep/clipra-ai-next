"""Verify Chromium's native H.264/AAC playback from a real FFmpeg MP4.

Browser navigation to HTTP/HTTPS is administratively blocked in this sandbox,
so a same-origin Blob URL is used to test actual MP4 decoding and playback.
Not a substitute for network Range handling or Safari/Android testing.
"""
from __future__ import annotations
import base64,json
from pathlib import Path
from playwright.sync_api import sync_playwright

root=Path(__file__).resolve().parents[1]
video=root/'evidence'/'verified-real-highbit-http-export.mp4'
assert video.exists(), 'The verified rendered MP4 is required for the playback test'
encoded=base64.b64encode(video.read_bytes()).decode('ascii')
with sync_playwright() as p:
    browser=p.chromium.launch(headless=True,executable_path='/usr/bin/chromium',args=[
        '--no-sandbox','--disable-dev-shm-usage','--autoplay-policy=no-user-gesture-required'])
    page=browser.new_page(viewport={'width':640,'height':480})
    page.set_content('<video id="clipraPlayback" controls playsinline autoplay muted style="width:100%;max-width:620px"></video>')
    results=page.evaluate('''async b64 => {
        const raw=atob(b64),arr=new Uint8Array(raw.length);
        for(let i=0;i<raw.length;i++)arr[i]=raw.charCodeAt(i);
        const video=document.getElementById('clipraPlayback');
        const url=URL.createObjectURL(new Blob([arr],{type:'video/mp4'}));
        const metadata=new Promise((resolve,reject)=>{
          video.onloadedmetadata=()=>resolve(true);
          video.onerror=()=>reject(Error('Native HTML5 video error '+video.error?.code));
        });
        video.src=url;
        await Promise.race([metadata,new Promise((_,reject)=>setTimeout(()=>reject(Error('Video metadata timeout')),8000))]);
        await video.play();
        await new Promise(r=>setTimeout(r,1000));
        const data={loaded:video.readyState>=2, duration:video.duration,
            width:video.videoWidth,height:video.videoHeight,currentTime:video.currentTime,
            codecSupport:video.canPlayType('video/mp4; codecs="avc1.42E01E, mp4a.40.2"'),
            bytes:arr.length, pageMode:'Blob URL, not HTTP navigation'};
        URL.revokeObjectURL(url);
        return data;
    }''',encoded)
    assert results['loaded'] and results['width']==1280 and results['height']==720
    assert 2.8<results['duration']<3.3 and results['currentTime']>0.3
    output=root/'evidence'/'chromium-native-mp4-playback.json'
    output.write_text(json.dumps({'status':'PASS','limitations':'Local Chromium Blob playback, not Safari/Android or HTTP Range playback',**results},indent=2))
    print(output.read_text())
    browser.close()