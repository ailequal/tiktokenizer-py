# syntax=docker/dockerfile:1

# Platforms: linux/amd64 and linux/arm64 (glibc, Debian trixie). tiktoken, regex and
# pydantic-core ship manylinux wheels for both; nothing here is architecture specific.
#
# Builder and runtime start from the same Python image digest, so the virtual environment
# copied between them points at the same interpreter path.
ARG PYTHON_IMAGE=python:3.14-slim-trixie@sha256:0514bc76712d64f8bb48adcb95b1ab0d88c69fee95d62fe4c18ee948bee9b1e1
ARG UV_IMAGE=ghcr.io/astral-sh/uv:0.13.5@sha256:32a7bb39b496babbd997b0a39a4d66c126bdaf5661b302bf6f06abda8deca6ff

FROM ${UV_IMAGE} AS uv

# --- base: Python plus uv, shared by every stage that installs dependencies --------------
FROM ${PYTHON_IMAGE} AS base
COPY --from=uv /uv /uvx /usr/local/bin/
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=0 \
    PYTHONUNBUFFERED=1
WORKDIR /app

# --- builder: locked install into /app/.venv, then download the BPE files ----------------
FROM base AS builder
ENV UV_NO_DEV=1
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --locked --no-install-project --no-editable
COPY pyproject.toml uv.lock README.md LICENSE .python-version ./
COPY src ./src
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-editable

# Needs network once, at build time; tiktoken verifies every file's SHA-256.
# Behind a proxy, pass --build-arg HTTPS_PROXY=... (a predefined build argument).
ENV TIKTOKEN_CACHE_DIR=/app/.tiktoken-cache
COPY scripts/warm_cache.py ./scripts/
RUN /app/.venv/bin/python scripts/warm_cache.py

# --- runtime: only the virtual environment and the BPE cache ------------------------------
FROM ${PYTHON_IMAGE} AS runtime
ARG VERSION=unknown
ARG REVISION=unknown
LABEL org.opencontainers.image.title="tiktokenizer-py" \
      org.opencontainers.image.description="Web playground for OpenAI tiktoken tokenizers" \
      org.opencontainers.image.licenses="MIT" \
      org.opencontainers.image.source="https://github.com/ailequal/tiktokenizer-py" \
      org.opencontainers.image.version="${VERSION}" \
      org.opencontainers.image.revision="${REVISION}"

RUN groupadd --system --gid 999 nonroot \
    && useradd --system --uid 999 --gid nonroot --home-dir /app --no-create-home nonroot \
    && install -d -o nonroot -g nonroot /app/data

WORKDIR /app
# Root-owned and read-only for the runtime user; nothing under /app is written at runtime.
COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/.tiktoken-cache /app/.tiktoken-cache

ENV PATH=/app/.venv/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    TIKTOKEN_CACHE_DIR=/app/.tiktoken-cache \
    APP_DATA_DIR=/app/data \
    UVICORN_HOST=0.0.0.0 \
    UVICORN_PORT=8000

# /app/data is the only path the app writes to (prices fetched from the page); compose.yaml
# mounts a named volume there so they survive restarts.
USER nonroot
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s --start-period=15s --retries=3 \
    CMD ["python", "-c", "import os, sys, urllib.request; port = os.environ.get('UVICORN_PORT', '8000'); sys.exit(0 if urllib.request.urlopen(f'http://127.0.0.1:{port}/healthz', timeout=2).status == 200 else 1)"]
CMD ["uvicorn", "tiktokenizer_py.main:app"]

# --- dev: full toolchain, source bind-mounted by compose, auto-reload ----------------------
FROM base AS dev
RUN groupadd --system --gid 999 nonroot \
    && useradd --system --uid 999 --gid nonroot --home-dir /app --no-create-home nonroot \
    && chown nonroot:nonroot /app \
    && install -d -o nonroot -g nonroot /app/data
USER nonroot
ENV UV_CACHE_DIR=/tmp/uv-cache \
    UV_FROZEN=1 \
    TIKTOKEN_CACHE_DIR=/app/.tiktoken-cache \
    APP_DATA_DIR=/app/data \
    UVICORN_HOST=0.0.0.0 \
    UVICORN_PORT=8000
COPY --chown=nonroot:nonroot pyproject.toml uv.lock README.md LICENSE .python-version ./
COPY --chown=nonroot:nonroot src ./src
RUN uv sync --all-groups
COPY --from=builder --chown=nonroot:nonroot /app/.tiktoken-cache /app/.tiktoken-cache
EXPOSE 8000
CMD ["uv", "run", "uvicorn", "tiktokenizer_py.main:app", "--reload", "--reload-dir", "src"]
