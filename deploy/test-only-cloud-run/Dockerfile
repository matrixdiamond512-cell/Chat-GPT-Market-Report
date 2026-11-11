FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PORT=8080
WORKDIR /app
COPY scripts/ /app/scripts/
COPY deploy/test-only-cloud-run/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir --requirement /app/requirements.txt
EXPOSE 8080
CMD ["functions-framework", "--source=scripts/reporting/cloud_run_testonly.py", "--target=cloud_run_http", "--host=0.0.0.0", "--port=8080"]
