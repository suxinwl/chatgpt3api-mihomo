# syntax=docker/dockerfile:1
FROM --platform=$BUILDPLATFORM node:22-alpine AS web
WORKDIR /web
COPY web/package.json web/package-lock.json ./
RUN npm ci --registry=https://registry.npmjs.org
COPY web/index.html web/vite.config.js ./
COPY web/src ./src
COPY web/public ./public
RUN npm run build

FROM --platform=$BUILDPLATFORM python:3.13-slim AS core
ARG TARGETARCH
WORKDIR /build
COPY upstream.json build_core.py ./
RUN python build_core.py "$TARGETARCH"

FROM python:3.13-slim
ARG VERSION=dev
ARG REVISION=unknown
LABEL org.opencontainers.image.title="chatgpt3api-mihomo" \
      org.opencontainers.image.description="Mihomo core with persistent subscription management" \
      org.opencontainers.image.source="https://github.com/suxinwl/chatgpt3api-mihomo" \
      org.opencontainers.image.version=$VERSION \
      org.opencontainers.image.revision=$REVISION \
      org.opencontainers.image.licenses="GPL-3.0-or-later"
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 DATA_DIR=/data COOKIE_SECURE=true
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates tzdata \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /opt/manager
COPY requirements.txt ./
RUN pip install --no-cache-dir --index-url https://pypi.org/simple -r requirements.txt
COPY --from=core /out/mihomo /usr/local/bin/mihomo
COPY --from=web /web/dist ./web/dist
COPY manager ./manager
COPY VERSION upstream.json LICENSE NOTICE ./
RUN mkdir -p /data && chmod 700 /data
EXPOSE 8080 7890
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/health',timeout=3)" || exit 1
CMD ["uvicorn", "manager.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8080", "--workers", "1", "--no-access-log"]
