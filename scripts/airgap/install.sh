#!/usr/bin/env bash
# Verify signature BEFORE extracting any package content.
# Rollback of a destructive database migration requires restoring the DB backup.
set -Eeuo pipefail
if [[ $# -ne 3 ]]; then
  echo "Usage: bash scripts/airgap/install.sh BUNDLE.tar BUNDLE.tar.sig TRUSTED_PUBLIC_KEY.pem" >&2
  exit 2
fi
bundle="$(realpath "$1")"; signature="$(realpath "$2")"; public_key="$(realpath "$3")"
for cmd in docker openssl sha256sum tar flock; do command -v "$cmd" >/dev/null || { echo "Missing $cmd" >&2; exit 2; }; done
openssl dgst -sha256 -verify "$public_key" -signature "$signature" "$bundle" || { echo "INVALID SIGNATURE" >&2; exit 1; }
# Only a correctly signed archive is ever unpacked.
stage="$(mktemp -d)"
trap 'rm -rf "$stage"' EXIT
mapfile -t members < <(tar -tf "$bundle")
allowed=$'images.tar\ncompose.release.yaml\nversion\ngit-commit\nSHA256SUMS'
[[ "$(printf '%s\n' "${members[@]}" | sort)" == "$(printf '%s\n' "$allowed" | sort)" ]] || { echo "Unexpected bundle entries" >&2; exit 1; }
# Archive entries must be regular files (no symlinks or hardlinks).
[[ "$(tar -tvf "$bundle" | awk '{print substr($1,1,1)}' | sort -u)" == "-" ]] || { echo "Non-regular archive members" >&2; exit 1; }
tar -C "$stage" -xf "$bundle"
(cd "$stage" && sha256sum -c SHA256SUMS)
version="$(cat "$stage/version")"
[[ "$version" =~ ^[a-zA-Z0-9][a-zA-Z0-9._-]*$ ]] || exit 1
if [[ ! -f .env ]]; then
  echo "Missing local .env; configure secrets before installation" >&2
  exit 1
fi
exec 9>.mice-update.lock
flock -n 9 || { echo "Another update is running" >&2; exit 1; }
backup_dir="./backups/airgap-$(date -u +%Y%m%dT%H%M%SZ)-$version"
mkdir -m 700 -p "$backup_dir"
cp -p .env "$backup_dir/env.backup"
[[ ! -e compose.release.yaml ]] || cp -p compose.release.yaml "$backup_dir/compose.release.yaml"
[[ ! -e .mice-version ]] || cp -p .mice-version "$backup_dir/previous-version"
# An existing installation requires a restorable database snapshot.
# Do not silently ignore pg_dump errors or continue with a partial backup.
if docker compose -f compose.release.yaml ps --status running --services 2>/dev/null | grep -qx db; then
  echo "Creating mandatory PostgreSQL backup..."
  docker compose -f compose.release.yaml exec -T db pg_dump -U mailfire -d mailfire -Fc > "$backup_dir/postgres.dump"
  [[ -s "$backup_dir/postgres.dump" ]] || { echo "Empty database backup" >&2; exit 1; }
elif [[ -e .mice-version ]]; then
  echo "Existing release has no running DB: start/recover it before upgrading" >&2
  exit 1
fi
# Preload images but leave application untouched until validation succeeds.
docker load -i "$stage/images.tar"
cp "$stage/compose.release.yaml" compose.release.yaml.next
MICE_VERSION="$version" docker compose -f compose.release.yaml.next config -q
# Release config changes only after all validations. Old volume is preserved.
mv compose.release.yaml.next compose.release.yaml
export MICE_VERSION="$version"
# Stop writers while schema is migrated. Do not stop the database.
docker compose -f compose.release.yaml stop api worker maintenance importer smtp parser web 2>/dev/null || true
# migrate service is one-shot; recreate so it cannot reuse a completed previous run.
docker compose -f compose.release.yaml up -d --no-build --pull never --wait db
docker compose -f compose.release.yaml up --no-build --pull never --force-recreate migrate
docker compose -f compose.release.yaml up -d --no-build --pull never --force-recreate --wait api worker maintenance importer smtp parser web
printf '%s\n' "$version" > .mice-version
echo "Release $version installed. Backup: $backup_dir"
echo "If schema migration fails, stop services and restore postgres.dump; container-only rollback is unsafe."
