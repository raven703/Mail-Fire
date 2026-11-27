#!/bin/sh
set -eu
umask 077
cd "$(dirname "$0")"
sha256sum -c SHA256SUMS
test ! -e .env || { echo 'Installation already initialized; use start.sh' >&2; exit 1; }
command -v docker >/dev/null
docker compose version
test "$(uname -m)" = x86_64
random() { od -An -N32 -tx1 /dev/urandom | tr -d ' \n'; }
PROJECT=mice-offline-$(random | cut -c1-12)
{
  echo "COMPOSE_PROJECT_NAME=$PROJECT"
  echo "DJANGO_SECRET_KEY=$(random)"
  echo "MICE_DB_PASSWORD=$(random)"
  echo "MICE_RABBIT_PASSWORD=$(random)"
  echo "ADMIN_PASSWORD=$(random)"
} > .env
. ./common.sh
docker load -i images.tar
dc up -d --no-build --pull never --wait --wait-timeout 180 db rabbitmq
dc run --rm --no-deps -T migrate python manage.py migrate --noinput
dc run --rm --no-deps -T migrate python manage.py shell -c 'exec(open("/bundle/restore_config.py").read())'
./start.sh
./verify.sh
echo 'Installed. Open http://127.0.0.1:18080 ; admin password is in .env (keep private).'