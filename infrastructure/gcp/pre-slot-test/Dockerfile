FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080
WORKDIR /app

COPY scripts/gcp/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir --requirement /tmp/requirements.txt

COPY scripts/ ./scripts/
COPY config/ ./config/
RUN mkdir -p /app/data/market /app/logs && \
    useradd --create-home --uid 10001 runner && \
    chown -R runner:runner /app
USER 10001

EXPOSE 8080
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--workers", "1", "--threads", "1", "--timeout", "300", "scripts.gcp.pre_slot_cloud_runner:application"]
