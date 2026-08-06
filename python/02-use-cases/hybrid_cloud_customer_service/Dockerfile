# AgentKit 0.5.5 uses Docker SDK's classic build endpoint. Default the base
# platform to amd64 so Apple Silicon builders do not reuse an arm64 layer, but
# keep it configurable to satisfy Dockerfile portability checks.
ARG RUNTIME_PLATFORM=linux/amd64
FROM --platform=${RUNTIME_PLATFORM} python:3.12-slim@sha256:cab2dbf575e971934a81e4622f5aba17aa7929719bd7e31033a3a83b97fd0464

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY requirements.lock ./
RUN pip install --no-cache-dir -r requirements.lock
COPY . /app
RUN chmod +x /app/entrypoint.sh \
    && mkdir -p /opt/application \
    && ln -s /app/entrypoint.sh /opt/application/run.sh \
    && addgroup --system --gid 10001 app \
    && adduser --system --uid 10001 --ingroup app --home /app --no-create-home app \
    && chown -R app:app /app /opt/application

EXPOSE 8000
USER app
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/docs', timeout=3)" || exit 1
ENTRYPOINT ["/app/entrypoint.sh"]
