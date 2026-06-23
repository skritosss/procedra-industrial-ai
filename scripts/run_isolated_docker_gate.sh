#!/bin/sh
set -eu

gate_image="industrial-instruction-ai:gate-$(date +%Y%m%d%H%M%S)"
gate_container="industrial-instruction-ai-gate-$$"
buildx_config="${TMPDIR:-/tmp}/industrial-ai-buildx-$$"

mkdir -p "$buildx_config"
export BUILDX_CONFIG="$buildx_config"

cleanup() {
    docker rm -f "$gate_container" >/dev/null 2>&1 || true
    docker image rm -f "$gate_image" >/dev/null 2>&1 || true
    rm -rf "$buildx_config"
}
trap cleanup EXIT INT TERM

echo "[1/5] Validate Compose configuration"
env -i PATH="$PATH" HOME="$HOME" BUILDX_CONFIG="$BUILDX_CONFIG" \
    docker compose --env-file /dev/null config >/dev/null

echo "[2/5] Build application image without changing the running container"
env -i PATH="$PATH" HOME="$HOME" BUILDX_CONFIG="$BUILDX_CONFIG" \
    docker compose --env-file /dev/null build industrial-instruction-ai

echo "[3/5] Build isolated verification image"
docker build --progress=plain --tag "$gate_image" --file - . <<'DOCKERFILE'
FROM industrial-instruction-ai:local
USER root
COPY . /app
RUN chown -R appuser:appuser /app
USER appuser
RUN python -m compileall -q app tests scripts
RUN ruff check app tests scripts
RUN mypy app scripts
RUN python -m pip check
RUN OPENAI_ENABLED=false python -m pytest -q
DOCKERFILE

echo "[4/5] Start hardened, isolated smoke container"
docker run --detach \
    --name "$gate_container" \
    --network none \
    --read-only \
    --cap-drop ALL \
    --security-opt no-new-privileges \
    --tmpfs /tmp:rw,nosuid,nodev,mode=1777,size=256m \
    --tmpfs /app/generated:rw,nosuid,nodev,uid=1000,gid=1000,mode=0700,size=256m \
    --tmpfs /app/uploads:rw,nosuid,nodev,uid=1000,gid=1000,mode=0700,size=256m \
    "$gate_image" >/dev/null

attempt=0
until docker exec "$gate_container" python -c \
    "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/ready', timeout=3).read()" \
    >/dev/null 2>&1
do
    attempt=$((attempt + 1))
    if [ "$attempt" -ge 30 ]; then
        docker logs "$gate_container"
        echo "Isolated /ready check timed out" >&2
        exit 1
    fi
    sleep 1
done

docker exec "$gate_container" python scripts/manage_database.py verify \
    --database /app/generated/app.sqlite3 >/dev/null

echo "[5/5] Gate passed; clean up temporary container and image"
echo "ISOLATED_DOCKER_GATE_OK"
