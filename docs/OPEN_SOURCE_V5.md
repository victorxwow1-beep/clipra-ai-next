# CLIPRA v5 — Evidence, open-source architecture and unresolved gaps

## What is actually integrated

- **SYSTRAN/faster-whisper** (MIT): the existing backend now imports and calls `WhisperModel(..., device='cpu', compute_type='int8')` for real audio transcription in Podcast/Education/Auto-without-visible-game-HUD workflows. The default `LOCAL_WHISPER_MODEL=tiny` downloads open model weights when analysis starts; requires Internet, RAM and CPU. Actual hosted model download and interpretation quality remain unverified until a real runtime job succeeds. Its **speech selection** prioritizes complete transcribed spoken stretches and does not pretend sound energy equals a good highlight. Up to N, not guaranteed N. Code: `backend/clipra/local_speech.py`.
- **Existing FFmpeg** open-source backend: resumable source upload (4 MiB chunks), original checksum, audio-preserving H264/AAC clip render, aspect Fit/Fill, preview and independent MP4 downloads. Added actual ZIP_STORED packaging, reject/delete and Render All.
- **Tesseract OCR + FFmpeg**: a strict game HUD text source-evidence path already existed; v5 connects it to a simplified smart request. It can detect limited visible strings such as “You eliminated,” **not necessarily confirm an actual player-owned kill**. It does not understand comedy, silent scenes, complex action, expressions or full scene story.
- **Mobile browser frontend** (first-party code on the same FastAPI site): one input-first UI, clip count Auto/3/5/10/Custom, clip length 15/24/30/60/custom minutes and seconds, content type, one main Find Best Clips action; review, edit/reject/download; advanced quality and cropping hidden until needed.

## GitHub upstream references studied, versus integrated

| Project | Role | License / actual use |
|---|---|---|
| [VideoHighlighter](https://github.com/Aseiel/VideoHighlighter) | Offline visual/audio/action ranking, explainable detectors, composition patterns | AGPL-3.0; **architecture studied, source code not copied**. Network use of modified code requires AGPL source obligations. |
| [SentrySearch](https://github.com/ssrajadh/sentrysearch) | Semantic video indexing, local Qwen3-VL, retrieval | Apache-2.0; reference reviewed. **Not deployed or integrated** because its local Qwen3-VL/Torch pipeline needs substantially more memory and model compute than has been verified for the existing Railway host. |
| [Qwen3-VL](https://github.com/QwenLM/Qwen3-VL) | Potential full multimodal game-event understanding | Apache-2.0 project; **not serving a model** on this free Railway host. No false visual-AI inference claimed. |
| [faster-whisper](https://github.com/SYSTRAN/faster-whisper) | Local speech-to-text model | MIT; **integrated as a library and CPU implementation**, provider installation tested by CI, real hosted weight download inference not yet proven. |
| [PySceneDetect](https://github.com/Breakthrough/PySceneDetect) | Precise camera scene boundaries and cut candidates | BSD-3-Clause; **reviewed but not yet connected** to the existing FFmpeg rendering pipeline. Scene changes alone cannot prove a highlight. |

The existing platform remains one password-protected studio at `https://clipra-studio-production.up.railway.app/`. The old Higgsfield `https://clipra-studio.higgsfield.app/` is an **independent browser-only prototype**; none of its credit/seek limitations should be mistaken for this separate server-backed project.

## Mobile + real video QA

- Core backend automated tests include real FFmpeg video upload, timing, exports, source audio, 9:16 fit, strict HUD text false positives and zero-evidence behavior.
- v5 tests cover real generated synthetic gaming video -> OCR candidate -> render H264/AAC -> ZIP with identical MP4 -> reject and file removal. Real Whisper library weights on actual speech are **not** shown as verified just because its import and mock protocol pass.
- `scripts/qa_mobile_browser.py` starts the real API + worker and uses Chromium Android-style emulation for source upload → model evidence → clip preview → playable MP4 ZIP → reject, plus WebKit iPhone-style screen and custom controls. These are **browser emulations, not real iPhones/Android devices**. Separate GitHub Action stores screenshots and video evidence if the run passes.
- `test_large_upload_v5.py` exercises 510 MiB via resumable chunks with source hash + ffprobe. The large file is synthetically padded, so it verifies transport/disk/metadata—not real 510 MiB high-bitrate decode, physical iPhone transfers, or 4-hour processing.
- Actual authorized YouTube/live import is best-effort, and a host-specific successful download has **not yet been demonstrated**. A YouTube iframe never becomes fake MP4 export.
- No physical iPhone Safari/Android QA; no paid plans activated; **server storage is ephemeral** with no Railway volume. Do not claim reliable production 24-hour jobs or durable media across restarts.

## Remaining requirements before calling it a full OpusClip-style semantic video AI

1. Deploy and test a free/open-source **video-capable** model (e.g. Qwen3-VL) on genuinely adequate owner-approved compute; sample continuous multi-frame clips and original audio and verify outputs on annotated actual PUBG WOW clips, podcasts and funny videos.
2. Collect real creator-owned gameplay and user-selected reference cuts; measure event recall, other-player false positives, missed jokes, and start/end errors. Reject low-confidence suggestions, do not force clip count.
3. Add durable media storage/queue checkpoints after user approves any provider charges, large-file cleanup and resource budgets, and re-run 30-minute/4-hour/24-hour stress tests.
4. Verify true local Whisper weight downloads and real audio transcripts, YouTube live importer on authorized video, browser WebKit/Chromium download and physical phone playback.
5. Any model failure must report **blocked/not configured**, never invent visual understanding, transcript, or clips.

## No paid AI requirement

Neither Higgsfield credits nor a Gemini API key is required for the v5 `/smart` endpoint. Local speech model weights may be free to obtain, but hosting CPU, RAM, storage, GPU and upload traffic are not necessarily free or unlimited. **Do not purchase or change the hosting plan without owner approval.**
