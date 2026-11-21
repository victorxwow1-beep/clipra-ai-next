#!/bin/sh
# Evaluation-only: an API and an independent worker process in one container.
# Multi-hour processing and reliable recovery require separately provisioned workers/storage.
set -eu
if [ -z "${CLIPRA_ADMIN_PASSWORD:-}" ] || [ -z "${CLIPRA_SESSION_SECRET:-}" ]; then
  echo 'Required server-side CLIPRA credentials are not configured.' >&2
  exit 1
fi
alembic upgrade head
python -m clipra.worker &
worker_pid=$!
trap 'kill "$worker_pid" 2>/dev/null || true' INT TERM EXIT
uvicorn clipra.main:app --host 0.0.0.0 --port "${PORT:-10000}" &
api_pid=$!
wait "$api_pid"