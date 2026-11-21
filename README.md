# CLIPRA AI NEXT — independent source repository

> **Status: new local engineering MVP, NOT a complete or deployed AI clipping service.**
> Old Higgsfield projects and files were not accessed, changed or reused.

CLIPRA NEXT takes real video bytes through a resumable upload API, verifies each original file, stores its hash, creates editable multi-segment edit decision lists, and renders **real H.264/AAC MP4 videos via FFmpeg from the original source**. It has a dependency-free first-party website served directly by FastAPI **plus** a Next.js frontend source (not yet built), a FastAPI API, a separate durable processing worker, SQLAlchemy/Alembic persistence, and an **opt-in** Google Gemini REST video-file analysis adapter. AI has **NOT** been tested with real credentials in this environment.

## Proven local flow

- 60-second 320×180 video **with audio** → streamed upload → hash and ffprobe validation → manual two-segment EDL → worker → real playable ~12-second H.264/AAC MP4 → full decode/ffprobe verification.
- **69.5 MiB** valid padded MP4 container → 4 MiB streamed chunks, interrupted/resumed HEAD offset → source inspection → rendered MP4. This exercises the upload-size regression, NOT realistic high-bitrate media decoding throughput.
- Invalid inputs rejected; Gemini without key returns `blocked` and creates NO fake AI clips.

Test file: `evidence/verified-manual-multisegment-export.mp4`. Code and tests in `backend/`.


## Current iteration — extra integration work (2026-11-21)

New direct Gemini REST video-file adapter (`clipra/gemini_rest.py`), bounded-memory FFmpeg visual/audio prefilter (`clipra/signals.py`), authorized YouTube reference-to-original-file linking, and a Chromium-mobile-DOM plus real FastAPI TestClient bridge QA. **20 local backend tests PASS**, browser-DOM bridge PASS with 16 backend requests. Neither is proof of live model understanding, real mobile media playback, or a production deployment. The model and media budget require user-supplied secure configuration and consent.

See [`docs/BUILD_PROGRESS_2026-11-21.md`](docs/BUILD_PROGRESS_2026-11-21.md) for current statuses and evidence. The prior evidence elsewhere in this README is historical and remains valid only for its stated scope.

## GitHub/Render handoff (November 21 follow-up)

GitHub plugin connection is now **verified** for user `victorxwow1-beep`, but there are **zero accessible repositories** and the plugin does not support creating a repository. A new private repo must be created on GitHub before the source can be pushed through the connector. Render has no services yet, and the free web-service filesystem is ephemeral. See [`docs/GITHUB_RENDER_HANDOFF_2026-11-21.md`](docs/GITHUB_RENDER_HANDOFF_2026-11-21.md).

This release adds GitHub Actions FFmpeg+Next CI and fixes concurrent edit/render conflicts and late-cancellation cleanup. **22 local backend tests pass.** AI inference and live website remain unverified until real provider credentials and deployment are available.

## Local setup

1. Install Docker Engine and Docker Compose; copy `.env.example` to `.env`.
2. Replace `CLIPRA_ADMIN_PASSWORD`, `CLIPRA_SESSION_SECRET`, `CLIPRA_DB_PASSWORD` with different strong random values.
3. Set `ALLOWED_ORIGINS=http://localhost:3000` and `COOKIE_SECURE=false` for LOCAL HTTP only.
4. `docker compose up --build` (not tested here; Docker is unavailable in the current runtime).
5. Visit `http://localhost:8000` for the dependency-free, full API-connected website, **or** `http://localhost:3000` for the Next.js frontend when its build succeeds. Authenticate, upload a video you have rights to process, and make manual clips.
6. By default AI is OFF. To enable: set a valid `GEMINI_API_KEY`, confirm provider supports actual video input, confirm user budget, set `ALLOW_EXTERNAL_AI=true` and restart worker/API. Each job separately requires consent. Real video inference remains unverified until a successful call and human-reviewed outputs.

The Next.js frontend dependency install timed out in the current sandbox (npm registry unavailable). TSX syntax was parsed but **Next.js build, Docker build, and browser E2E are NOT verified**.

## Website that runs with the backend

The production-source folder `backend/clipra/site` is a first-party responsive HTML/CSS/JavaScript website. FastAPI serves it at `/` and serves `/studio-assets/*`; upload, login, AI consent, EDL editing, clip rendering, previews, and downloads call the real FastAPI API. It does **not** depend on npm or Next.js. A real backend and worker are required for its actual jobs. FastAPI route and static assets pass TestClient smoke checks; browser navigation is blocked by the sandbox administrator, so browser interaction and physical mobile testing remain **unverified**.

## Local backend without Docker

```bash
cd backend
python -m pip install -r requirements.txt 'alembic>=1.14,<2'
export DATABASE_URL=sqlite:////tmp/clipra-next.db
export MEDIA_ROOT=/tmp/clipra-next-media
export CLIPRA_ADMIN_PASSWORD='your-own-long-random-password'
export CLIPRA_SESSION_SECRET='your-own-long-random-signing-secret'
alembic upgrade head
uvicorn clipra.main:app --host 127.0.0.1 --port 8000
# In a second shell, with the same env vars:
python -m clipra.worker
```

`cd frontend && npm install && npm run dev` in a JS runtime with access to npm registry.

## API surface

`POST /api/auth/login`, `GET /api/me`, `POST /api/uploads`, `HEAD/PATCH /api/uploads/{id}`, `POST /api/uploads/{id}/complete`, `GET /api/media`, `GET /api/media/{id}`, `GET /api/media/{id}/stream`, `POST /api/media/{id}/analyze`, `POST/GET /api/media/{id}/clips`, `PUT /api/clips/{id}`, `POST /api/clips/{id}/render`, `GET /api/jobs/{id}`, `POST /api/jobs/{id}/cancel`, `POST /api/jobs/{id}/retry`, `GET /api/clips/{id}/preview`, `GET /api/clips/{id}/download`, `POST /api/youtube/inspect`, `GET /api/providers`, `GET /health`, `GET /ready`.

## Architecture

`Next.js (mobile browser) → FastAPI authenticated upload, media and EDL API → PostgreSQL (SQLite only for dev) → separate worker → local persistent named volume → FFmpeg original source encoder / Gemini video window adapter (opt-in)`.

No FFmpeg is executed inside an HTTP route. Render and analyze jobs are queued in SQL; workers pick them up with row locking under PostgreSQL. Media remains on a dedicated volume. The production target is S3-compatible object storage, but it is **not implemented**. Redis is not required by the current SQL queue. This is deliberate for a minimal working core.

## Verification

```bash
PYTHONPATH=backend python -m pytest backend/tests -q
cd backend && PYTHONPATH=. DATABASE_URL=sqlite:////tmp/clipra-next-new.db alembic upgrade head
```

See `docs/QA_REPORT.md`, `docs/FEATURE_STATUS.md`, `docs/PROVIDERS.md`, `docs/DEPLOYMENT.md`, and `docs/SECURITY.md` for limits and remaining work.

## November 21 additional verified regression

A newly encoded, **68.686 MiB** (not padded) H.264/AAC synthetic video passed the live FastAPI HTTP upload → interruption/resume → verification → manual edit → background FFmpeg render → playable MP4 download pipeline. Details and new test scripts are in `docs/TEAM_AND_LIVE_QA.md`. Browser, actual Gemini intelligence, public deployment, and mobile-device tests still **must not** be called PASS.

## Temporary single-host evaluation (new)

The root `Dockerfile` and `deploy/start.sh` can run the first-party FastAPI website and a separate FFmpeg worker process in a **single** evaluation container, for a low-cost proof of public URL deployment. This is not a durable production architecture: the host filesystem may be wiped after restart, and no real Gemini credentials or authorized YouTube video media retrieval are configured. Read `deploy/EVALUATION_ONLY.md` before using.