# CLIPRA AI NEXT — implementation, evidence and blockages

**Snapshot: 2026-11-21.** This is a new independent local Git project, not a deployed public service or completed AI clipper. No old Higgsfield resource was changed; no billed service or API key was provisioned.

## Completed this iteration

1. Implemented `clipra/gemini_rest.py` — a direct, server-side Google Gemini Files REST adapter. It uploads actual MP4 bytes, waits for activation, makes a structured video inference request, sanitizes provider errors, and removes the uploaded temporary file on the normal path. Tests use `httpx.MockTransport` against documented HTTP routes, including actual MP4 bytes and an untrusted upload URL rejection. **This does not prove the actual Gemini account works, or that its clips are meaningful.**
2. Built `clipra/signals.py` — bounded-memory FFmpeg visual frame-difference and audio RMS signal sampling, which selects limited costly AI windows on long inputs. These are NOT semantic AI highlights. Long video coverage is explicitly marked incomplete.
3. Implemented `POST /api/media/{id}/youtube` to associate an owner-authorized, original file with a YouTube reference. The original file is still the source for real MP4 renders. Google documentation separately supports YouTube URLs for *video understanding*, not source media export. Identity matching is based on owner attestation only.
4. Improved the dependency-free browser UI's AI availability messaging and disabled its AI action when server credentials are missing or outbound analysis is disabled. Added YouTube reference linking.
5. Added `scripts/test_browser_ui_bridge.py` — actual Chromium at 390px renders the first-party UI and runs DOM actions over a bridge to a real FastAPI TestClient. **Login, Gallery file upload, YouTube reference link, manual clip EDL, FFmpeg job, and download control passed in one test, with 16 real backend requests.** This cannot establish native video playback or unrestricted browser networking, since this environment disallows page navigation.
6. Added three signal tests, seven Gemini HTTP contract and security/fault-injection tests, and the YouTube association-to-actual-MP4 render test. Existing real 60-second, authentic high-bitrate 68.686 MiB and MP4-decoding tests remain.

## Independent review

n8n Victor AI Team — Master Orchestrator reviewed the engineering strategy again (execution **67**, succeeded). Its lead reported that specialist results were incomplete or cut off, so the team feedback is **advice, not source-code verification**. We implemented priority safety recommendations: delete uploaded Google files on processing failure and validate the upload destination's exact TLS origin, port and user-info. Tests assert delete-on-error and reject malicious provider upload URL variants.

## Additional browser codec verification

Actual Chromium HTML5 `video` playback of the earlier FFmpeg H.264/AAC export via a local Blob URL **PASS**: 1280×720, 3.021333 seconds, playback advanced past 0.9 seconds. See `evidence/chromium-native-mp4-playback.json`. This does NOT test website network loading, iPhone/Android, or HTTP Range playback.

## Evidence available

- `PYTHONPATH=backend pytest backend/tests -q`: **20 PASS** on 2026-11-21. Some FastAPI/httpx deprecation warnings; none are failures.
- `python scripts/test_browser_ui_bridge.py`: **PASS**; saved mobile screenshot `evidence/browser-ui-bridge-390px.png`. A video element may show an infinite loader in this bridged test because normal media network navigation is blocked.
- `evidence/verified-real-highbit-http-export.mp4`: previously tested, genuine FFmpeg output from a 68.686 MiB encoded source. See `evidence/real-69mb-http-e2e.json`.
- `evidence/verified-manual-multisegment-export.mp4`: earlier manual two-section timeline export, H.264/AAC.

## Current feature status

| Feature | Status |
|---|---|
| File upload >48 MiB with chunked resume, SHA-256, original preservation | **VERIFIED WORKING locally** |
| FFprobe validation, manual EDL, independent FFmpeg H.264/AAC MP4, authenticated download | **VERIFIED WORKING locally** |
| Browser login, upload, project, editor, export controls | **VERIFIED WORKING in Chromium DOM + real-backend bridge**; not normal network navigation or mobile playback |
| Google Files REST adapter | **IMPLEMENTED — CONTRACT TESTED ONLY**, no live credentials |
| Content-aware AI-selected clips | **BLOCKED** — no verified video model invocation or editorial annotations |
| Local A/V signal candidate discovery | **VERIFIED WORKING as nonsemantic prefilter** |
| YouTube reference link to authorized original | **VERIFIED WORKING locally** |
| Direct YouTube-URL semantic analysis with user's Gemini key | **NOT IMPLEMENTED**; official provider capability documented, key not verified |
| YouTube-only to MP4 without authorized media bytes | **BLOCKED / UNSUPPORTED**; metadata/video understanding alone is not actual source bytes |
| Long-video checkpointing (4h/24h), S3 object storage, hard AI spending controls, multi-user roles | **NOT IMPLEMENTED** |
| Next.js production build | **NOT VERIFIED** — npm registry cannot resolve in current runtime |
| Public production URL / real iPhone Safari | **NOT VERIFIED** — no writable Git remote, no deployed service, browser navigation blocked |

## Safe next gates

1. Add the user's Gemini video-capable credential in their **private secret manager**, not in chat. Keep `ALLOW_EXTERNAL_AI=false` until the user approves video transmission/budget. `GEMINI_VIDEO_MODEL` is configurable; `models.get` verifies existence only, not video understanding. Run real authored/annotated media with consent and evaluate timestamp accuracy, false positives, quality and MP4 outputs.
2. Connect a new writable Git repository, not the abandoned Higgsfield repository. Do not create a paid host or database without explicit approval. Render shows an accessible workspace but zero services and the local repo has no remote; a public production URL cannot truthfully be claimed.
3. Build/test Next.js on a runner with npm access, and run actual network browser + physical Safari/Android tests on deployed HTTPS before public launch.
4. Complete user isolation, quotas, cleanup/retention, rate limiting, container-sandbox validation, and signed object-store URLs before opening the service to the public.

## Official provider context

- [Gemini video understanding](https://ai.google.dev/gemini-api/docs/video-understanding) documents video files and, in preview, video understanding from YouTube URLs. Analyzing a URL does not provide the audiovisual file for FFmpeg export.
- [Gemini Files API](https://ai.google.dev/api/files) documents file uploads, file activation, temporary access, and multimodal generateContent.
- [Render deployment](https://render.com/docs/web-services) requires a deployment source such as a connected repository or an image. Current connector `create_web_service` is limited to Git-backed sources.