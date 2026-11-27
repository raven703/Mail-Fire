#!/bin/sh
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cd "$ROOT"
test -f .env || { echo 'Run ./install.sh first' >&2; exit 1; }
PROJECT=$(sed -n 's/^COMPOSE_PROJECT_NAME=//p' .env)
case "$PROJECT" in mice-offline-*) ;; *) echo 'Unsafe project name' >&2; exit 1;; esac
dc() { docker compose --env-file "$ROOT/.env" -p "$PROJECT" -f "$ROOT/compose.offline.json" "$@"; }