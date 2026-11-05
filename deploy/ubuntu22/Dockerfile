FROM python:3.12-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    MPLBACKEND=Agg \
    MPLCONFIGDIR=/tmp/ecg-matplotlib \
    OMP_NUM_THREADS=2 \
    OPENBLAS_NUM_THREADS=2 \
    MKL_NUM_THREADS=2 \
    ECG_LOG_LEVEL=INFO \
    ECG_HUNTER_DATABASE=/app/web/runtime/heartbeat_hunter.sqlite3

WORKDIR /app
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 libstdc++6 libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

COPY deploy/ubuntu22/requirements-runtime.txt /tmp/requirements-runtime.txt
RUN python -m pip install --no-cache-dir --only-binary=:all: -r /tmp/requirements-runtime.txt \
    && python -m pip install --no-cache-dir --no-deps --only-binary=:all: \
       --index-url https://download.pytorch.org/whl/cpu 'torch==2.14.1+cpu' \
    && python -m pip check

COPY . /app
RUN useradd --uid 10001 --create-home --shell /usr/sbin/nologin ecg \
    && mkdir -p /app/web/runtime \
    && chown ecg:ecg /app/web/runtime \
    && python deploy/ubuntu22/verify_bundle.py --files-only

USER ecg
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=10s --start-period=90s --retries=3 \
    CMD ["python", "deploy/ubuntu22/healthcheck.py"]
CMD ["python", "-m", "uvicorn", "web.backend.production:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
