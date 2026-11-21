# CLIPRA AI NEXT — Live launch status (21 November 2026)

## Published source: VERIFIED

GitHub: https://github.com/victorxwow1-beep/clipra-ai-next

This repository contains a genuine FastAPI video-upload service, FFmpeg video renderer, separate worker, responsive first-party website, Next.js source, opt-in Gemini adapter and tests. Tests are local and **do not** prove a public deployment.

## Live hosting: BLOCKED

A Render **Free** Docker web-service creation was attempted with the user's authorization. Render returned HTTP 402, requiring payment information. No service was created, no charge was authorized or made, and no live URL exists. Do not put secrets into chat or public GitHub files. A suitable account/host with free or approved compute access is needed before deployment.

## Feature truth table

| Capability | Status |
| --- | --- |
| Gallery / Files upload, resumable and checksum verification | Locally verified with real ~68.7 MiB video |
| Manual clips generated from source by FFmpeg | Locally verified, decoded playable H.264/AAC MP4 |
| Browser shell and backend API integration | Locally tested; public browser deployment pending |
| Automatic multimodal highlight discovery | Gemini REST adapter written and contract-mocked; **not real-inference verified** |
| YouTube links | Metadata check and authorized original-file association only; YouTube link alone does **not** produce MP4 |
| Livestreams / multi-hour / 24-hour videos | Not end-to-end verified |
| Durable multi-user hosting | Not implemented |
| iPhone physical-device full upload/save | Not verified |

## What remains

Connect a deployment account that allows building a Docker container with FFmpeg and an authorized durable media store. Before sharing any public URL, verify backend readiness, worker health, authenticated upload, full MP4 export/download, and user data retention. Real Gemini credentials need secure hosting secrets and informed user consent; per-job spend limits must be configured. Do not conflate an AI API model response with source-video media delivery.

## Security

No private keys, production password, uploaded media or credentials should ever be committed to GitHub. On ephemeral evaluation hosts, uploads and exports can disappear on restart or idle suspension. Use original-file copies only.
