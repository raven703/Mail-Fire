#!/usr/bin/env bash
# Build a self-contained, signed offline Docker release.
set -Eeuo pipefail
cd "$(dirname "$0")/../.."
if [[ $# -ne 3 ]]; then
  echo "Usage: bash scripts/airgap/build.sh VERSION SIGNING_PRIVATE_KEY OUTPUT_DIR" >&2
  exit 2
fi
version="$1"; signing_key="$2"; output_dir="$3"
[[ "$version" =~ ^[a-zA-Z0-9][a-zA-Z0-9._-]*$ ]] || { echo "Invalid version" >&2; exit 2; }
for cmd in docker openssl sha256sum tar git; do command -v "$cmd" >/dev/null || { echo "Missing $cmd" >&2; exit 2; }; done
[[ -f "$signing_key" ]] || { echo "Missing private key" >&2; exit 2; }
signing_key="$(realpath "$signing_key")"
mkdir -p "$output_dir"
output_dir="$(realpath "$output_dir")"
stage="$(mktemp -d)"
trap 'rm -rf "$stage"' EXIT
# Offline target never builds. Network access is used only here.
docker build --target final -t "mice/backend:$version" .
docker build -t "mice/web:$version" ./frontend
docker pull --platform "$(docker version --format '{{.Server.Os}}/{{.Server.Arch}}')" pgvector/pgvector:pg17
docker pull --platform "$(docker version --format '{{.Server.Os}}/{{.Server.Arch}}')" clamav/clamav:stable
docker save -o "$stage/images.tar" "mice/backend:$version" "mice/web:$version" pgvector/pgvector:pg17 clamav/clamav:stable
cp compose.release.yaml "$stage/compose.release.yaml"
printf '%s\n' "$version" > "$stage/version"
git rev-parse HEAD > "$stage/git-commit"
# Manifest hash list covers every payload item, including Docker image archive.
(cd "$stage" && sha256sum images.tar compose.release.yaml version git-commit > SHA256SUMS)
bundle="$output_dir/mice-release-$version.tar"
tar -C "$stage" -cf "$bundle" images.tar compose.release.yaml version git-commit SHA256SUMS
openssl dgst -sha256 -sign "$signing_key" -out "$bundle.sig" "$bundle"
printf 'Created %s and %s.sig\n' "$bundle" "$bundle"
