set dotenv-load := true
set shell := ["sh", "-cu"]

image := "tiktokenizer-py:local"
platforms := "linux/amd64 linux/arm64"

# Image labels: the version comes from pyproject.toml, the revision from git.
export IMAGE_VERSION := `uv version --short 2>/dev/null || echo unknown`
export IMAGE_REVISION := `git rev-parse --short HEAD 2>/dev/null || echo unknown`

# Host-side BPE cache inside the project (gitignored); the image sets its own path.
export TIKTOKEN_CACHE_DIR := env("TIKTOKEN_CACHE_DIR", justfile_directory() / ".tiktoken-cache")

# Where prices fetched from the page are saved on the host (gitignored); the image uses /app/data.
export APP_DATA_DIR := env("APP_DATA_DIR", justfile_directory() / ".app-data")

# List all recipes
default:
    @just --list

# --- setup -----------------------------------------------------------------

# One-shot bootstrap for a fresh clone
setup: install cache-warm

# Install the project and the dev group into .venv
install:
    uv sync --all-groups

# Refresh uv.lock without upgrading
lock:
    uv lock

# Upgrade every dependency to the latest version allowed by pyproject.toml
upgrade:
    uv lock --upgrade

# Download every BPE file into $TIKTOKEN_CACHE_DIR
cache-warm:
    uv run python scripts/warm_cache.py

# Refresh the bundled price snapshot from OpenAI's official pages; review with git diff
prices-update:
    uv run python scripts/update_prices.py

# --- develop ---------------------------------------------------------------

# Run uvicorn with auto-reload on the host
dev:
    uv run uvicorn tiktokenizer_py.main:app --reload --reload-dir src --port ${APP_PORT:-8000}

# Run uvicorn without reload on the host
run:
    uv run uvicorn tiktokenizer_py.main:app --port ${APP_PORT:-8000}

# Tokenize from the command line: just tokenize gpt-5 "hello world"
[positional-arguments]
tokenize model text *flags:
    uv run tiktokenizer-py "$@"

# --- quality ---------------------------------------------------------------

# Format the code
fmt:
    uv run ruff format .
    uv run ruff check --fix .

# Lint and check formatting
lint:
    uv run ruff check .
    uv run ruff format --check .

# Type-check the package
typecheck:
    uv run mypy

# Run the test suite, extra arguments go to pytest
[positional-arguments]
test *args:
    uv run pytest "$@"

# Run the test suite with a coverage report; fails below 85%
cov:
    uv run pytest --cov=tiktokenizer_py --cov-report=term-missing --cov-fail-under=85

# CI gate: lint, type-check and test
check: lint typecheck test

# --- docker ----------------------------------------------------------------

# Build the production image for the host platform
docker-build:
    docker build --target runtime --build-arg VERSION="$IMAGE_VERSION" --build-arg REVISION="$IMAGE_REVISION" \
        -t {{ image }} .

# Run the production image on http://localhost:${APP_PORT:-8000}, with settings from .env
docker-run: docker-build
    docker run --rm -p "127.0.0.1:${APP_PORT:-8000}:8000" $([ -f .env ] && echo --env-file .env) {{ image }}

# Offline smoke test: no network, read-only root, non-root user, every encoding loads
docker-smoke: docker-build
    #!/bin/sh
    set -eu
    cid=$(docker run -d --network none --read-only --tmpfs /tmp --cap-drop ALL \
        --security-opt no-new-privileges:true {{ image }})
    trap 'docker rm -f "$cid" >/dev/null' EXIT
    status=starting
    for _ in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20 21 22 23 24 25 26 27 28 29 30; do
        status=$(docker inspect -f '{{{{.State.Health.Status}}' "$cid")
        [ "$status" = healthy ] && break
        sleep 1
    done
    echo "health: $status"
    [ "$status" = healthy ]
    test "$(docker exec "$cid" id -u)" != 0
    docker exec "$cid" python -c "import json, urllib.request; from tiktokenizer_py import tokenizers; [print(n, json.load(urllib.request.urlopen(urllib.request.Request('http://127.0.0.1:8000/api/tokenize', json.dumps({'model': n, 'text': 'hello world'}).encode(), {'content-type': 'application/json'})))['tokens']) for n in tokenizers.all_encoding_names()]"
    echo "smoke test passed"

# Foreign platforms run under emulation (Docker Desktop, or binfmt/QEMU on Linux).

# Build and smoke-test the image for linux/amd64 and linux/arm64, without pushing
docker-build-multi:
    #!/bin/sh
    set -eu
    for platform in {{ platforms }}; do
        arch=${platform#linux/}
        tag="{{ image }}-$arch"
        echo "--- build $platform as $tag"
        docker buildx build --platform "$platform" --target runtime --load \
            --build-arg VERSION="$IMAGE_VERSION" --build-arg REVISION="$IMAGE_REVISION" -t "$tag" .
        echo "--- run $platform"
        docker run --rm --platform "$platform" --network none --read-only "$tag" \
            python -c "import platform; from tiktokenizer_py import tokenizers; tokenizers.warm_up(); print(platform.machine(), tokenizers.resolve('gpt-5').encode('hello world'))"
    done

# Start the production-like stack on localhost, and on the proxy hostname when it runs
up: && _urls
    docker compose --profile dev stop dev
    docker compose up --build --detach --wait app || { just _port-hint; exit 1; }

# Start the dev container with the source bind-mounted and auto-reload
up-dev:
    docker compose stop app
    docker compose --profile dev up --build dev || { just _port-hint; exit 1; }

_port-hint:
    @echo "If the error above says port ${APP_PORT:-8000} is already in use, pick a free one:"
    @echo "  APP_PORT=8010 just up    (or set APP_PORT in .env)"

# Print where the app answers; the proxy hostname only if it really routes to the app
_urls:
    #!/bin/sh
    echo "http://localhost:${APP_PORT:-8000}"
    for _ in 1 2 3; do
        if curl -sf --max-time 1 http://tiktokenizer-py.spark.loc/healthz >/dev/null 2>&1; then
            echo "http://tiktokenizer-py.spark.loc"
            exit 0
        fi
        sleep 1
    done
    echo "(http://tiktokenizer-py.spark.loc works too once the SparkFabrik HTTP proxy runs: spark-http-proxy start)"

# Stop every service
down:
    docker compose --profile dev down

# Follow the logs of the running services
logs:
    docker compose --profile dev logs --follow

# Open a shell in the dev container
shell:
    docker compose --profile dev run --rm --build dev sh

# Run the test suite inside the dev image
[positional-arguments]
docker-test *args:
    docker compose --profile dev run --rm --build dev uv run pytest "$@"

# Check the SparkFabrik HTTP proxy and the route to this app
proxy-status:
    spark-http-proxy status
    spark-http-proxy hosts describe tiktokenizer-py.spark.loc

# --- misc ------------------------------------------------------------------

# Print the model and encoding catalogue
models:
    uv run python -c "from tiktokenizer_py.catalogue import print_table; print_table()"

# Remove local caches and the virtual environment
clean:
    rm -rf .venv .pytest_cache .mypy_cache .ruff_cache .hypothesis htmlcov .coverage
