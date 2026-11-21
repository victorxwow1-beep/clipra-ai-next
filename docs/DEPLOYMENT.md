# Deployment path and boundaries

**No live CLIPRA NEXT service was deployed.** Existing Render workspace was inspected read-only. It was not provisioned or billed.

1. Install / connect a Git hosting provider with repo write permissions; push this *new* Git repository without `.env` or any original media. Do not point deployment to abandoned Higgsfield project.
2. Use a trusted container host with persistent volume, PostgreSQL, an independent FFmpeg worker, and request routing for Next.js, or route public HTTPS directly to the API container serving the dependency-free first-party UI at `/`. `docker-compose.yml` is a local reference only, not a hardened production deployment recipe.
3. Review runtime limits, external egress restrictions, host firewall, TLS termination and storage ownership. Create durable secrets in host secret manager. `COOKIE_SECURE=true`, `ALLOWED_ORIGINS=https://<your-domain>`.
4. Deploy migration (`cd backend && alembic upgrade head`) before API and worker. The Compose `migrate` service represents this order.
5. Add dedicated object storage and signed URLs before running for many users or on ephemeral hosts. Current volume sharing can work only where the API/worker share a persistent volume.
6. Test full frontend build and HTTP reverse proxy. Then repeat video upload → manual / consented AI inference → render → download on the deployed URL.
7. Do not enable Gemini or paid infrastructure without explicit budget approval. Limit maximum media size to actual free capacity; add quotas, retention and safeguards.

### Known infrastructure gaps

No Docker binary or frontend npm package registry access was available in the sandbox. Therefore Docker images, Compose networking, PostgreSQL runtime, real browser behavior and hosted output require verification. A Render workspace existing is not authorization to provision paid resources.