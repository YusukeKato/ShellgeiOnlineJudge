#!/bin/sh
set -eu

if [ -z "${DOCKER_HOST:-}" ]; then
    : "${XDG_RUNTIME_DIR:?XDG_RUNTIME_DIR is required for rootless Docker}"
    DOCKER_HOST="unix://${XDG_RUNTIME_DIR}/docker.sock"
    export DOCKER_HOST
fi

case "${DOCKER_HOST}" in
    unix://*)
        DOCKER_SOCKET_PATH=${DOCKER_SOCKET_PATH:-${DOCKER_HOST#unix://}}
        export DOCKER_SOCKET_PATH
        ;;
    *)
        echo "Error: DOCKER_HOST must point to a local rootless Unix socket." >&2
        exit 1
        ;;
esac

case "$(docker info --format '{{json .SecurityOptions}}')" in
    *'name=rootless'*) ;;
    *)
        echo "Error: refusing to run Docker Compose against a rootful daemon." >&2
        exit 1
        ;;
esac

exec docker compose "$@"
