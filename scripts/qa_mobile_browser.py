#!/usr/bin/env python3
"""End-to-end mobile browser QA against the real FastAPI + FFmpeg worker.

Runs actual server, logs in, uploads an MP4, invokes source-grounded smart
analysis, downloads rendered clips as a ZIP and rejects a clip. WebKit uses
mobile iPhone-sized browser emulation; Chromium uses Android-sized emulation.
A browser emulator is NOT a physical Safari or Android device certificate.
"""
from __future__ import annotations
import os
import re
import subprocess
import tempfile
import time
import urllib.request
from pathlib import Path
from zipfile import ZipFile

from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[1]
PASSWORD="clipra-mobile-qa-secret-strong"
URL="http://127.0.0.1:9987"


def source_file(directory:Path)->Path:
    out=directory/"real-browser-qa.mp4"
    overlay="drawtext=text='You eliminated the opponent':fontsize=55:fontcolor=white:x=65:y=300:enable='between(t,2,7)'"
    subprocess.run([
        "ffmpeg","-hide_banner","-loglevel","error","-y",
        "-f","lavfi","-i","color=c=black:s=640x360:r=12:d=10",
        "-f","lavfi","-i","sine=frequency=440:sample_rate=48000:duration=10",
        "-vf",overlay,"-c:v","libx264","-preset","ultrafast",
        "-pix_fmt","yuv420p","-crf","28",
        "-c:a","aac","-b:a","96k","-shortest","-movflags","+faststart",str(out)
    ],check=True,timeout=90)
    return out


def wait_http():
    for _ in range(100):
        try:
            with urllib.request.urlopen(URL+"/health",timeout=1) as response:
                if response.status==200:return
        except Exception:pass
        time.sleep(.3)
    raise RuntimeError("The actual CLIPRA API never became healthy")


def check_qa_mode(playwright, browser_name:str, source:Path, screenshots:Path, *,
                  full_pipeline:bool):
    browser_type=getattr(playwright,browser_name)
    browser=browser_type.launch(headless=True)
    try:
        if browser_name=="webkit":
            context=browser.new_context(viewport={"width":390,"height":844},
                            is_mobile=True,has_touch=True,device_scale_factor=3,
                            accept_downloads=True)
        else:
            context=browser.new_context(viewport={"width":412,"height":915},
                            is_mobile=True,has_touch=True,device_scale_factor=2.625,
                            accept_downloads=True)
        page=context.new_page()
        page.goto(URL,wait_until="domcontentloaded",timeout=30000)
        page.locator("#password").fill(PASSWORD)
        page.locator("#loginForm button[type=submit]").click()
        page.get_by_text("Turn videos into clips.").wait_for(timeout=30000)
        assert page.locator("#count").count()==1
        assert page.locator("#length").count()==1
        assert page.locator("#category").count()==1
        page.locator("#count").select_option("3")
        page.locator("#length").select_option("24")
        page.locator("#category").select_option("gaming")
        page.locator("#ratio").select_option("original")
        page.locator("#file").set_input_files(str(source))
        page.locator("#rights").check()
        assert "real-browser-qa.mp4" in page.content()
        screenshots.mkdir(parents=True,exist_ok=True)
        page.screenshot(path=str(screenshots/(browser_name+"-home.png")),full_page=True)
        if full_pipeline:
            page.get_by_role("button",name=re.compile("Find Best Clips")).click()
            page.locator(".clipcard video").wait_for(state="attached",timeout=240000)
            page.screenshot(path=str(screenshots/(browser_name+"-clips.png")),full_page=True)
            preview=page.locator(".clipcard video").first
            preview.wait_for()
            # Browser availability is distinct from physical phone codec playback.
            codec=page.evaluate('''() => ({
              canPlay:document.createElement("video").canPlayType('video/mp4; codecs="avc1.42E01E"'),
              clipSource:document.querySelector(".clipcard video")?.getAttribute("src")
            })''')
            assert "/api/clips/" in codec["clipSource"],codec
            with page.expect_download(timeout=45000) as item:
                page.get_by_role("link",name=re.compile("Download All ZIP")).click()
            download=item.value
            zip_path=screenshots/(browser_name+"-real-clips.zip")
            download.save_as(str(zip_path))
            with ZipFile(zip_path) as z:
                names=z.namelist()
                assert len(names)==1 and names[0].endswith(".mp4")
                clip=screenshots/(browser_name+"-verified-export.mp4")
                clip.write_bytes(z.read(names[0]))
            probed=subprocess.check_output(["ffprobe","-v","error","-show_entries",
                "stream=codec_name","-of","csv=p=0",str(clip)],text=True,timeout=25)
            assert "h264" in probed and "aac" in probed,probed
            page.on("dialog",lambda d:d.accept())
            page.get_by_role("button",name="Reject").click()
            page.get_by_text("No verified clips yet").wait_for(timeout=10000)
            print(browser_name,"real clip+ZIP verified; canPlay H.264:",codec["canPlay"])
        else:
            page.locator("#count").select_option("custom")
            page.locator("#customCount").fill("7")
            page.locator("#length").select_option("custom")
            page.locator("#customMinutes").fill("1")
            page.locator("#customSeconds").fill("15")
            assert page.locator("#customSeconds").input_value()=="15"
            page.screenshot(path=str(screenshots/(browser_name+"-custom-options.png")),full_page=True)
            print(browser_name,"mobile input UX verified; no rendering claimed")
        context.close()
    finally:browser.close()


def main():
    with tempfile.TemporaryDirectory(prefix="clipra-browser-qa-") as tmp:
        td=Path(tmp);source=source_file(td)
        environment=os.environ.copy()
        environment.update({
            "PYTHONPATH":str(ROOT/"backend"),
            "CLIPRA_ADMIN_PASSWORD":PASSWORD,
            "CLIPRA_SESSION_SECRET":"clipra-mobile-tests-cookie-secret-long-enough",
            "DATABASE_URL":"sqlite:///"+str(td/"test.db"),
            "MEDIA_ROOT":str(td/"media"),
            "COOKIE_SECURE":"false","ALLOW_EXTERNAL_AI":"false"
        })
        log=(td/"server.log").open("w")
        api_proc=subprocess.Popen(["python","-m","uvicorn","clipra.main:app",
                                   "--host","127.0.0.1","--port","9987"],
                                  cwd=ROOT,env=environment,stdout=log,stderr=log)
        worker_proc=None
        try:
            wait_http()
            worker_proc=subprocess.Popen(["python","-m","clipra.worker"],
                    cwd=ROOT,env=environment,stdout=log,stderr=log)
            screenshots=ROOT/"qa-browser-artifacts"
            with sync_playwright() as pw:
                check_qa_mode(pw,"chromium",source,screenshots,full_pipeline=True)
                check_qa_mode(pw,"webkit",source,screenshots,full_pipeline=False)
        finally:
            for p in (worker_proc,api_proc):
                if p and p.poll() is None:
                    p.terminate()
                    try:p.wait(timeout=6)
                    except subprocess.TimeoutExpired:p.kill()
            log.close()
            print((td/"server.log").read_text(errors="replace")[-2000:])

if __name__=="__main__":main()
