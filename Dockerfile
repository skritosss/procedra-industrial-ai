FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    OPENAI_ENABLED=false \
    OPENAI_TIMEOUT_SECONDS=10 \
    VIDEO_MAX_BYTES=262144000 \
    VIDEO_MAX_DURATION_SECONDS=1800 \
    VIDEO_NETWORK_TIMEOUT_SECONDS=15 \
    VIDEO_JOB_LEASE_SECONDS=600 \
    VIDEO_JOB_HEARTBEAT_SECONDS=15 \
    VIDEO_JOB_POLL_SECONDS=1 \
    VIDEO_JOB_MAX_ATTEMPTS=3 \
    VIDEO_JOB_DOWNLOAD_TIMEOUT_SECONDS=900 \
    VIDEO_JOB_EXTRACT_TIMEOUT_SECONDS=900 \
    VIDEO_JOB_ANALYSIS_TIMEOUT_SECONDS=900 \
    VIDEO_JOB_STAGE_POLL_SECONDS=0.25 \
    VISION_MAX_KEYFRAMES=8 \
    VISION_MAX_IMAGE_BYTES=5242880 \
    DOCUMENT_MAX_BYTES=15728640 \
    DATABASE_PATH=/app/generated/app.sqlite3 \
    METRICS_DATABASE_PATH=/app/generated/metrics.sqlite3 \
    METRICS_BUCKET_SECONDS=60 \
    METRICS_WINDOW_SECONDS=300 \
    METRICS_RETENTION_SECONDS=604800 \
    METRICS_LATENCY_THRESHOLD_MS=2000 \
    METRICS_AVAILABILITY_SLO_PERCENT=99 \
    METRICS_LATENCY_SLO_PERCENT=95 \
    METRICS_ALERT_MIN_REQUESTS=20 \
    PUBLIC_SOURCES_ENABLED=true \
    PUBLIC_SOURCES_MAX_RESULTS=15

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ffmpeg \
        fonts-dejavu-core \
        libgl1 \
        libglib2.0-0 \
        libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --upgrade pip \
    && pip install -r requirements.txt

COPY app ./app
COPY examples ./examples
COPY scripts/cleanup_artifacts.py ./scripts/cleanup_artifacts.py
COPY scripts/manage_database.py ./scripts/manage_database.py
COPY scripts/reconcile_document_ownership.py ./scripts/reconcile_document_ownership.py
COPY scripts/run_video_job_worker.py ./scripts/run_video_job_worker.py
COPY README.md ./

RUN useradd --create-home --shell /usr/sbin/nologin appuser \
    && mkdir -p /app/generated/keyframes /app/uploads/videos /app/generated/instructions /app/uploads/documents \
    && chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/ready', timeout=3).read()"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
