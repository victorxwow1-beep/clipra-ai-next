# Provider and API evidence

## Connected environment inspection (2026-11-21)

- n8n is connected, with an accessible personal project and AI-team workflows. Its `list_credentials` returned **0 user-visible credential metadata objects**. Managed Gateway coverage includes model nodes for Google Gemini and others. This does **not** establish a generic Gemini video-capable API key exposed to CLIPRA backend.
- Existing Gemini Bridge accepts chat text. Its presence does not mean video files may be uploaded and analyzed by this new backend.
- Aggregated/multi-provider API: provider name, scope and secret are **not exposed** by these connectors. `AGGREGATOR_API_KEY` and `AGGREGATOR_PROVIDER` are configuration placeholders; NO aggregator video adapter is verified or active.
- Gemini REST adapter in `backend/clipra/ai.py` uploads a genuinely encoded audio+video proxy window through Google Files REST API, waits for the video file to activate, calls a configurable `GEMINI_VIDEO_MODEL`, validates structured evidence/timestamps, and creates a clip candidate only after a real model response. **No live key or video request was tested.** Default disabled.
- Model selection: example `gemini-3.5-flash` is a configurable identifier, not an account-specific availability claim. Check currently available, video-capable models and price through the actual key before enabling.
- Spending protection: default `ALLOW_EXTERNAL_AI=false` and bounded `MAX_AI_WINDOWS=4`, no enabled billing or paid services. Per-job returned token counts are recorded when real inference runs. **Hard monetary ceilings and per-provider billing verification NOT implemented.** Enable only with explicit budget approval.
- YouTube Data API `videos.list` returns structured video information, **not audiovisual source bytes**. The application supports reference validation and instructs the owner to provide original authorized media. Metadata lookup with user key and link-to-file association are future work.

## Useful source documentation

- Gemini video understanding: https://ai.google.dev/gemini-api/docs/video-understanding
- Gemini Files API: https://ai.google.dev/api/files
- YouTube Data API `videos.list`: https://developers.google.com/youtube/data/reference/rest/v3/videos/list
- YouTube API policies: https://developers.google.com/youtube/terms/developer-policies
- tus resumable upload protocol: https://github.com/tus/tus-resumable-upload-protocol/blob/main/protocol.md

## No surprises principle

Do not paste keys in chat, commit them, store them in client JS or mix backend configuration with public env vars. Use secret manager/environment only. Disable outbound requests until the user has explicitly consented to external analysis for the specific source.

### 2026-11-21 implementation clarification

The new adapter in `backend/clipra/gemini_rest.py` uses actual multipart-equivalent Google resumable upload requests, structured `generateContent` with file URI, and server-side secret header. The HTTP request contract is tested with a fake Google transport, including verifying actual video bytes. **No external Gemini inference ran.** `GEMINI_VIDEO_MODEL` defaults to a documented example but MUST be checked against the real account model catalog, quotas and costs. The old `google-genai` package is no longer required for this REST implementation.

The official Gemini Interactions API documents YouTube URLs for video understanding, but this does not convey exportable source video bytes, and CLIPRA does not yet implement the Interactions YouTube-URL mode. Current YouTube linkage stores a reference against the separately supplied authorized original.

Google upload cleanup is now attempted in both successful analysis completion and failed activation, and malicious upload URLs with user-info, non-TLS or nonstandard ports are rejected by the adapter. A persistent cleanup sweeper is still missing.