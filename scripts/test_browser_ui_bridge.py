"""Browser DOM + actual backend integration without network navigation.

Chromium's administrator denies URL navigation in this environment. We inject the
real served HTML/CSS/JS into about:blank, and translate fetch to a real FastAPI
TestClient. This tests real browser UI events and backend behavior; it does NOT
claim normal browser navigation, video playback or real network behavior.
"""
from __future__ import annotations
import json, os, tempfile, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))


def run():
    from playwright.sync_api import sync_playwright
    from fastapi.testclient import TestClient
    from clipra.main import app
    from clipra.worker import run_pending
    password='qa-only-browser-password-012345'
    os.environ['CLIPRA_ADMIN_PASSWORD']=password
    os.environ['CLIPRA_SESSION_SECRET']='qa-only-browser-session-very-long-and-random'
    os.environ['ALLOW_EXTERNAL_AI']='false'
    with tempfile.TemporaryDirectory(prefix='clipra-browser-') as td:
        os.environ['MEDIA_ROOT']=str(Path(td)/'media')
        # Imported db.Session is bound to an engine initialized on import. Use fresh process with env already set.
        with TestClient(app) as client:
            fixture=Path(td)/'fixture.mp4'
            p=subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-nostdin','-y','-f','lavfi',
               '-i','testsrc2=size=320x180:rate=24','-f','lavfi','-i','sine=frequency=440:sample_rate=44100',
               '-t','6','-c:v','libx264','-preset','ultrafast','-crf','30','-c:a','aac','-b:a','64k',str(fixture)],capture_output=True)
            assert p.returncode==0,p.stderr.decode()
            site=client.get('/').text
            css=client.get('/studio-assets/style.css').text
            js=client.get('/studio-assets/app.js').text
            http_calls=[]
            def bridge(arg):
                url=arg.get('url','')
                assert url.startswith('/api/'), url
                method=arg.get('method','GET')
                body=arg.get('body')
                if isinstance(body,list):body=bytes(body)
                resp=client.request(method,url,content=body,headers=arg.get('headers') or {})
                http_calls.append({'method':method,'path':url,'status':resp.status_code})
                return {'status':resp.status_code,'headers':dict(resp.headers),'text':resp.text if 'video/' not in resp.headers.get('content-type','') else ''}
            with sync_playwright() as p:
                browser=p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox','--disable-dev-shm-usage'])
                page=browser.new_page(viewport={'width':390,'height':844})
                page.expose_function('__bridgeFetch',bridge)
                page.add_init_script('''
                    window.__memoryStorage = {};
                    Object.defineProperty(window,'localStorage',{configurable:true,value:{
                        getItem(k){return window.__memoryStorage[k]??null},
                        setItem(k,v){window.__memoryStorage[k]=String(v)},
                        removeItem(k){delete window.__memoryStorage[k]}
                    }});
                ''')
                page.set_content(site,wait_until='domcontentloaded')
                # add_init_script only runs on document navigation, not set_content
                page.evaluate('''() => {
                    window.__memoryStorage = {};
                    Object.defineProperty(window,'localStorage',{configurable:true,value:{
                        getItem(k){return window.__memoryStorage[k]??null},
                        setItem(k,v){window.__memoryStorage[k]=String(v)},
                        removeItem(k){delete window.__memoryStorage[k]}
                    }});
                }''')
                page.evaluate('''() => {
                    window.fetch = async (url, options={}) => {
                        let body=options.body||null;
                        if (body instanceof Blob) body=Array.from(new Uint8Array(await body.arrayBuffer()));
                        const value=await window.__bridgeFetch({url:String(url),method:options.method||'GET',headers:options.headers||{},body});
                        return {ok:value.status>=200&&value.status<300,status:value.status,
                            headers:new Headers(value.headers),
                            json:async()=>JSON.parse(value.text||'null'),
                            text:async()=>value.text};
                    };
                }''')
                page.add_style_tag(content=css)
                page.add_script_tag(content=js)
                page.get_by_label('Workspace password').fill(password)
                page.get_by_role('button',name='Open workspace').click()
                page.get_by_text('Import your original video').wait_for(timeout=6000)
                page.locator('input[type=file]').set_input_files(str(fixture))
                page.get_by_text('I own this video or have permission').click()
                page.locator('[data-act="upload"]').click()
                page.locator('video.player').wait_for(timeout=12000)
                assert page.locator('video.player').count()==1
                # Missing Gemini credentials must not offer a fake working AI button.
                assert not page.locator('[data-act="analyze"]').is_enabled()
                page.locator('#linkedYt').fill('https://youtu.be/dQw4w9WgXcQ')
                page.locator('[data-act="linkYoutube"]').click()
                page.get_by_text('Linked your authorized original').wait_for(timeout=6000)

                page.locator('[data-act="save"]').click()
                page.get_by_role('button',name='Render MP4').wait_for(timeout=10000)
                page.get_by_role('button',name='Render MP4').click()
                # jobs need worker in separate process in prod; process directly here
                assert run_pending(max_jobs=1)==1
                page.get_by_text('Download ↓').wait_for(timeout=10000)
                assert page.locator('video[src*="/api/clips/"]').count()>0
                screenshot=ROOT/'evidence'/'browser-ui-bridge-390px.png'
                page.screenshot(path=str(screenshot),full_page=True)
                print(json.dumps({'test':'real Chromium DOM + FastAPI TestClient bridge',
                    'result':'PASS','page':'390px mobile','source_video_bytes':fixture.stat().st_size,
                    'http_calls':len(http_calls),'rendered_download_control':True,'screenshot':str(screenshot),
                    'limitation':'No network navigation, no native video playback, no physical Safari/Android browser test'},indent=2))
                browser.close()

if __name__=='__main__':
    # Configure the database before importing clipra modules
    os.environ.setdefault('DATABASE_URL','sqlite:////tmp/clipra-next-browser-qa-20261121.sqlite')
    run()