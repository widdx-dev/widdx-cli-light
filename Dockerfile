# ===========================================================================
# WIDDX Nexus — Docker Image (Production-Ready)
# ===========================================================================
# Build:
#   docker build -t widdx/nexus:latest .
#
# Run:
#   docker run -d --name widdx-web -p 8000:8000 widdx/nexus:latest
# ===========================================================================

FROM python:3.13-slim

LABEL org.opencontainers.image.title="WIDDX Nexus"
LABEL org.opencontainers.image.description="Terminal AI Workspace with UIL Cognitive Architecture — Production Ready"
LABEL org.opencontainers.image.authors="MUHAMMAD MUSLIH (WIDDX)"
LABEL org.opencontainers.image.url="https://github.com/widdx1990/widdx-cli-light"
LABEL org.opencontainers.image.licenses="MIT"
LABEL org.opencontainers.image.version="3.2.0"

# ── System dependencies ──────────────────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    nodejs \
    npm \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# ── Create widdx user (non-root) ─────────────────────────
RUN useradd --create-home --shell /bin/bash widdx \
    && mkdir -p /workspace /workspace/.widdx/data \
    && chown -R widdx:widdx /workspace

# ── Install Python package ───────────────────────────────
WORKDIR /opt/widdx
RUN pip install --no-cache-dir --upgrade pip

# ── Copy application files ───────────────────────────────
COPY --chown=widdx:widdx . .

RUN pip install --no-cache-dir ".[api]"

# ── Health check ─────────────────────────────────────────
# يتأكد من أن الخادم مستجيب كل 30 ثانية
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -sf http://localhost:8000/api/health \
    -H "Authorization: Bearer ${WIDDX_API_KEY:-healthcheck}" \
    || exit 1

# ── Switch to non-root user ──────────────────────────────
USER widdx

# ── Environment ──────────────────────────────────────────
ENV WIDDX_HOME=/workspace
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

WORKDIR /workspace

# ── Entry point ──────────────────────────────────────────
# widdx-web (افتراضي) أو widdx-api أو widdx أو widdx-tui
ENTRYPOINT ["widdx-web"]
CMD ["--host", "0.0.0.0", "--port", "8000"]
