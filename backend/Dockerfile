FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg && rm -rf /var/lib/apt/lists/*
RUN groupadd -g 10001 clipra && useradd -u 10001 -g 10001 -m clipra && mkdir -p /data/media && chown clipra:clipra /data/media
WORKDIR /srv
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && pip install --no-cache-dir 'alembic>=1.14,<2'
COPY clipra ./clipra
COPY alembic.ini ./
COPY migrations ./migrations
ENV PYTHONPATH=/srv
USER clipra
CMD ["uvicorn", "clipra.main:app", "--host", "0.0.0.0", "--port", "8000"]