"""The site is served from the real backend, not an inert mockup."""

def test_website_loads_and_calls_backend(client):
    homepage=client.get('/')
    assert homepage.status_code==200
    assert 'CLIPRA AI NEXT' in homepage.text
    assert '/studio-assets/app-v5.js' in homepage.text
    js=client.get('/studio-assets/app-v5.js')
    css=client.get('/studio-assets/style-v5.css')
    assert js.status_code==200 and css.status_code==200
    assert b"'/api'+path" in js.content
    assert b"/clips/" in js.content
    assert b'Download All ZIP' in js.content