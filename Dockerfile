FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
WORKDIR /app

COPY requirements-p1-cloudrun.txt ./
RUN python -m pip install --no-cache-dir --disable-pip-version-check \
    -r requirements-p1-cloudrun.txt

COPY config/report_schedule.json ./config/report_schedule.json
COPY scripts/resolve_market_report_slot.py ./scripts/
COPY scripts/report_continuity_shadow.py ./scripts/
COPY scripts/report_continuity_gcs.py ./scripts/
COPY scripts/report_continuity_ingress.py ./scripts/
COPY scripts/run_report_continuity_service.py ./scripts/

USER 65532:65532
CMD ["sh", "-c", "exec gunicorn --bind 0.0.0.0:${PORT:-8080} --workers 1 --threads 1 --timeout 120 scripts.run_report_continuity_service:app"]
