"""The site is served from the real backend, not an inert mockup."""

def test_website_loads_and_calls_backend(client):
    homepage=client.get('/')
    assert homepage.status_code==200
    assert 'CLIPRA AI NEXT' in homepage.text
    assert '/studio-assets/app.js' in homepage.text
    js=client.get('/studio-assets/app.js')
    css=client.get('/studio-assets/style.css')
    assert js.status_code==200 and css.status_code==200
    assert b"'/api'+path" in js.content
    assert b"/clips/" in js.content
    assert b'FFmpeg' in homepage.content or b'FFmpeg' in js.content