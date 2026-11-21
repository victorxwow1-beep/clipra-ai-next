# GitHub and Render launch handoff — independently checked 2026-11-21

## GitHub connector evidence

- Connected account: `victorxwow1-beep`.
- Installed app ID: `184337385`, installation `repository_selection=all`.
- `list_repositories` and owner-affiliation list: **zero repositories**.
- GitHub connector exposes writing to existing repositories but no `create_repository` operation. Do not invent a repo or claim one was published.
- No GitHub remote is configured in this local checkout (`git remote -v` empty).

### One required account action

Open `https://github.com/new`, create a **new private, empty** repository named `clipra-ai-next` under `victorxwow1-beep` (do not add a README, license or template yet). The existing GitHub App installation has `all` repository selection, so it should expose newly created repositories without changing access settings. The authenticated connector must still **recheck** visibility and push permission before publishing.

The source is ready for either a GitHub API tree+commit push after repo creation, or a normal Git push using the included Git bundle. Do not connect this project to the abandoned Higgsfield codebase.

## Render evidence and constraints

- Accessible Render workspace: `tea-dbvvobe7bikc7390rarg`.
- `list_services`: empty. No live website or URL exists for CLIPRA AI NEXT.
- Render requires a real Git URL for the relevant `create_web_service` action; local `sandbox:/mnt/data` artifacts are not a remote Git provider.
- Render free web services have **ephemeral filesystem** and sleep during inactivity. Uploaded videos, SQLite projects and exports are lost after restarts without durable infrastructure. A free web instance must never be represented as durable production video hosting.
- Production needs persisted object storage (not yet implemented), a durable database, a separate isolated worker, and a hosting plan that handles FFmpeg workloads. Paid provisioning requires explicit approval.

Official references: https://render.com/docs/free , https://render.com/docs/disks , https://render.com/docs/web-services

## Source fixes and tests in this release

- Existing full video flow: resumable media upload, ffprobe/FFmpeg validation, manual EDL, genuine H.264/AAC MP4 export, browser DOM/HTTP integration checks.
- Added test that **blocks edit mutations during queued or running renders**, avoiding stale exported material after a concurrent edit.
- Added worker cleanup for **late cancellations after FFmpeg had published an output file**; cancelled exports are no longer downloadable.
- Added GitHub Actions CI to test the real FFmpeg pipeline plus Next.js frontend build, and to reject tracked known secret filenames.
- Executed local `PYTHONPATH=backend python -m pytest backend/tests -q`: **22 passed**. GitHub CI not run until a repository exists.

## Important incomplete work

- Real Gemini-video inference with the user's secured credential: **blocked/unverified**. Mock HTTP provider contract tests are not proof of semantic video analysis.
- Independent public URL, deployment, and iPhone Safari QA: **blocked/unverified**.
- 1–24-hour video durability, signed S3 uploads, per-user isolation, native iOS save, multi-user auth, long-video load tests: **not verified or incomplete**.
- Do not upload private media to Google without explicit consent and operating-budget approval.

## Next actions after a private repo exists

1. Recheck GitHub repository visibility, default branch and push permissions.
2. Publish this **new** source, excluding `.env`, media originals, caches and credentials; verify commit SHA and CI.
3. Choose a durable Render architecture and budget, set secrets in Render settings, deploy API + worker + database + storage, and test the public service.
4. Execute a consented real Gemini-video file smoke test and measure AI highlight accuracy against human annotations. Never mark AI as verified based only on mock transports.