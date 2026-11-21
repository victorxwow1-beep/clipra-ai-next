# CLIPRA AI NEXT — Deployment and feature status (21 November 2026)

## Railway-hosted evaluation: VERIFIED DEPLOYED (not production certified)

- Public domain: https://clipra-studio-production.up.railway.app
- Railway project: `fab86bcf-8c3f-4d4e-998d-f6fa2f9d9f03`
- Railway service: `b1112995-08a7-4480-aae0-ecc4705bd58b`
- Deployment: `89a20350-6852-42af-8da7-286f51bb0490` — terminal status **SUCCESS**.
- Runtime: Alembic migration succeeded, Uvicorn started, Railway internal `GET /health` returned 200 OK.
- Public routing: an external HTTPS POST to `/health` reached the app and returned the expected 405 Method Not Allowed (the health endpoint is GET-only). Full public browser walkthrough and real hosted MP4 export remain **unverified**.
- Auth: high-entropy owner password configured in Railway secrets; **not committed to GitHub**.
- Plan: newly created Railway account with Free Trial credit. No paid plan was deliberately activated. Usage can consume the limited free credits.
- WARNING: SQLite and originals/exports are on the temporary container filesystem. On host restart, redeploy, or sleep, media and DB may be deleted. Preserve your originals elsewhere. Do not use with irreplaceable or confidential media.

## Feature truth table

| Capability | Status |
| --- | --- |
| Gallery / Files resumable upload | Locally VERIFIED with real 68.7 MiB video |
| Manual video clipping with FFmpeg | Locally VERIFIED: H.264/AAC playable MP4 |
| Hosting of website + API + worker | Railway deployment SUCCESS, runtime health passed |
| Public site and external routing | HTTPS public domain reached app; full browser workflow pending |
| Automatic Gemini-selected clips | Adapter IMPLEMENTED; real model inference NOT VERIFIED; external AI disabled |
| YouTube reference association | IMPLEMENTED, but link alone does NOT deliver authorized source bytes or MP4 |
| YouTube link-to-MP4 | NOT IMPLEMENTED |
| Durable production-grade media storage | NOT IMPLEMENTED |
| Multi-hour/livestream 24-hour workload | NOT VERIFIED |
| Physical iPhone Safari upload/save | NOT VERIFIED |

## Next engineering priorities

1. Test authenticated real public upload → FFmpeg render → browser MP4 playback/download.
2. Fix any hosted upload/worker failures with deployment logs.
3. Implement secure durable storage and backup retention controls (requires resource cost approval before provisioning).
4. Verify real Gemini video-capable API credential and editorial quality using consented original media; limit usage/cost per job.
5. Implement legitimate authorized YouTube media ingestion; do not confuse metadata/understanding with downloadable bytes.

**Do not call this a finished OpusClip competitor or production-safe system.** Existing Higgsfield project remains untouched.
