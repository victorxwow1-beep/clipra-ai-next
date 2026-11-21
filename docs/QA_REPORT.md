# CLIPRA AI NEXT — Evidence-based local QA

**Date:** 2026-11-21
**Test location:** isolated local development container, FFmpeg 7.1.5, Python 3.13.5, FastAPI TestClient.
**Scope:** genuine backend upload/render, source integrity, minimal readiness checks. **No claim of production certification.**

**Website extension:** Built a dependency-free responsive first-party UI served at FastAPI `/` (no npm requirement). Tested HTML, JavaScript and CSS paths via real TestClient and ran `node --check` on the JS (success). Attempted Playwright Chromium direct localhost and an in-memory FastAPI route; both navigation attempts were denied `net::ERR_BLOCKED_BY_ADMINISTRATOR`. This is an environment browser policy: **no interactive browser E2E claim**. Backend video render tests remain independently valid.

## Executed

- `PYTHONPATH=backend python -m pytest backend/tests -q`: **8 passed** (~4.8s on local generated source). Relevant warnings: FastAPI deprecated `on_event` and httpx raw-byte test API usage.
- `alembic upgrade head` on clean SQLite test DB: **success**, schema at `5a55645e9c42`.
- TypeScript TSX parser (globally installed TypeScript): both `frontend/app/page.tsx` and `layout.tsx` **zero syntax diagnostics**. Dependency installation timed out; **not** a type-check or runtime proof.

### Test A: real local processing (PARTIAL relative to user requirement)
Generated an owned 60-second 320×180 test video with 48 kHz sine audio via FFmpeg. Uploaded in chunks with interruption simulation, SHA-256 matches original, ffprobe confirmed video and audio. Created manual EDL [5–11s, 22–28s], worker rendered H.264/AAC. Download tested through authenticated endpoint; output `evidence/verified-manual-multisegment-export.mp4` is playable and fully decoded by FFmpeg. Duration ~12s, original source hash unchanged.
**Missing:** Gemini did not run; these boundaries are manual, not AI-selected. No iPhone device verification.

### Test B: prior 48 MB regression (PARTIAL)
Generated a **valid MP4** by appending an MP4 `free` atom to the same 60-second video, up to **69.5 MiB**. Uploaded in **4 MiB chunks**, checked server HEAD offset, resumed, validated/inspected, and rendered a 2-second clip. Tests passed. This is a valid high-size container transport test, not a real high-bitrate video or real network interruption test.

### Test B follow-up: real high-bitrate media (PASS for local transport → MP4 pipeline)
A second regression used a genuinely FFmpeg-encoded **68.686 MiB**, 35-second 1280x720 H.264/AAC MP4 (not a padded free atom). Through a **running FastAPI HTTP server**, 18 x 4 MiB PATCH chunks uploaded, HEAD verified a midway resume offset, final checksum matched, FFmpeg inspected the media, the worker rendered a manual 3-second clip, and the HTTP download fully decoded. Original hash unchanged. Video/audio codecs were H.264/AAC, and duration was 3.021333s. See `evidence/real-69mb-http-e2e.json` and `docs/TEAM_AND_LIVE_QA.md`. This is still not a real physically disconnected network, a human gameplay annotation, AI inference, or mobile browser test.

### Additional tested cases

- Upload offset mismatch correctly returns HTTP 409.
- Duplicate queued analyze requests return the same job ID; a queued job cancels correctly.
- Out-of-bounds timeline segment correctly returns HTTP 422.
- Actual 9:16 **fit/pad** FFmpeg export succeeds at 1080×1920.

### Test C: gaming semantic intelligence (BLOCKED)
No owned annotated gameplay file or independently callable Gemini video credential was available to this runtime. The app blocks semantic inference without the configured key instead of pretending a highlight exists.

### Test D: other genres (NOT VERIFIED)
Podcast, livestream, education and drama inference have prompt-specific implementation but no real files, human annotation, or accuracy metrics.

### Test E: export integrity (PARTIAL)
ffprobe checked duration, width/height, presence of video/audio; explicit tests checked H.264 and AAC. Whole output was decoded with FFmpeg and returned success. Accurate visual boundary assessment and subjective editing quality are pending.

### Test F: mobile (NOT VERIFIED)
No iPhone Safari or Android browser test. Original media preview and rendered clip playback use HTML video, and rendered MP4 download is a normal browser response. Native iOS Photos saving is not claimed.

### Test G: YouTube (PARTIAL)
HTTPS YouTube IDs validated; code returns explicit `requires_authorized_original`, never fake media bytes. Actual YouTube API key and authorized media delivery provider were not verified.

### Test H: reliability (PARTIAL)
Positive tests cover resumable offset, invalid file rejection, missing AI credentials. Worker process architecture and cancellation checks exist. Full process-kill recovery, large file storage pressure, 4h/24h, quotas, S3 cleanup, real network loss and concurrent races are **not tested**.

## n8n independent architecture review
Existing **Victor AI Team — Master Orchestrator** successfully executed manual review, execution IDs **65 and 66**. Qwen QA/security and Kimi returned recommendations; some engineering/reliability specialists were empty. Advice included worker isolation, validating assembled media, consent-based Gemini, original file preservation, distinguishing YouTube metadata from media, and not claiming lossless precision with re-encode. This was a **design review, not code inspection, live Gemini validation, or end-to-end QA**.

## Conclusion
**Real manual MP4 pipeline VERIFIED LOCALLY. Semantic AI-to-MP4 generation NOT VERIFIED. Frontend build and deployment NOT VERIFIED.** Do not market the product as fully working AI clipping yet.