# CLIPRA AI NEXT: single-host, evaluation-only API + FFmpeg worker.
# Free hosts may delete /tmp on restart; use durable storage before production.
FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg tesseract-ocr libgl1 libglib2.0-0 ca-certificates && rm -rf /var/lib/apt/lists/*
WORKDIR /srv
COPY backend/requirements.txt /srv/requirements.txt
RUN pip install --no-cache-dir -r /srv/requirements.txt 'alembic>=1.14,<2'
# Bake the real open-weight CPU model at build time: no user API key or
# first-video download. Do not load a 2B+ multimodal model into 1 GiB RAM.
RUN mkdir -p /srv/whisper-cache && python -c "from faster_whisper import WhisperModel; WhisperModel('tiny',device='cpu',compute_type='int8',download_root='/srv/whisper-cache')" && chmod -R a+rX /srv/whisper-cache
ENV LOCAL_WHISPER_MODEL=tiny WHISPER_CACHE_DIR=/srv/whisper-cache WHISPER_OFFLINE=true WHISPER_CPU_THREADS=2
COPY backend/clipra /srv/clipra
COPY backend/migrations /srv/migrations
COPY backend/alembic.ini /srv/alembic.ini
COPY deploy/start.sh /srv/start.sh
RUN groupadd -g 10001 clipra && useradd -u 10001 -g 10001 -m clipra && chmod 755 /srv/start.sh
ENV PYTHONPATH=/srv PYTHONUNBUFFERED=1
USER clipra
EXPOSE 10000
CMD ["/srv/start.sh"]