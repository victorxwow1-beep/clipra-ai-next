# Temporary live evaluation host

This Docker root service serves the existing real FastAPI website and FFmpeg worker on one host. It is **not production-grade**. The SQLite database, original uploads, pending jobs and exported files are on the host filesystem, not durable cloud object storage. On hosts such as Render Free, these can disappear on a restart/redeploy. Do not upload irreplaceable recordings; keep the original copies.

The service requires securely configured `CLIPRA_ADMIN_PASSWORD` and `CLIPRA_SESSION_SECRET`; never commit them or disclose in chat. All new uploads require rights confirmation. External Gemini AI is disabled unless a real key is added, `ALLOW_EXTERNAL_AI=true` and the user separately consents to each analysis. YouTube video links alone never give authorized video bytes and do not produce MP4s. Pair each reference with an authorized original file.

Test only: `/health`, owner login, small MP4 upload, manual EDL, export and download. Check account password, cookies, upload limits and errors before sharing the URL. No user registration or public multiuser access is implemented.

Do not present this as a finished OpusClip-style product.