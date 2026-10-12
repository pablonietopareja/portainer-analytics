FROM python:3.14.6-slim-bookworm@sha256:4c92ffcde4dd6f1ff72a24518f49fd4990b27134987dfa31a733badde66df9f8 AS dependencies
WORKDIR /build
COPY requirements.txt ./
RUN python -m venv /opt/venv \
    && /opt/venv/bin/python -m pip install --no-cache-dir --require-hashes -r requirements.txt

FROM python:3.14.6-slim-bookworm@sha256:4c92ffcde4dd6f1ff72a24518f49fd4990b27134987dfa31a733badde66df9f8
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 \
    CONSOLE_HOST=0.0.0.0 CONSOLE_PORT=8082 CONSOLE_DATA_DIR=/data
LABEL org.opencontainers.image.title="Portainer Analytics" \
    org.opencontainers.image.version="alpha.3"
WORKDIR /app
RUN groupadd --gid 10001 analytics \
    && useradd --uid 10001 --gid analytics --no-create-home analytics \
    && mkdir /data && chown analytics:analytics /data
COPY --from=dependencies /opt/venv /opt/venv
COPY portainer_console.py engine.py persistence.py dashboard_metrics.py telemetry.py VERSION ./
COPY web ./web
USER 10001:10001
VOLUME ["/data"]
EXPOSE 8082
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8082/api/health', timeout=3)"
CMD ["python", "portainer_console.py"]
