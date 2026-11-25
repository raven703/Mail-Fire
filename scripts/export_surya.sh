#!/bin/sh
set -eu
root=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
out=${1:?usage: export_surya.sh ABSOLUTE_OUTPUT_DIRECTORY}
case "$out" in /*) ;; *) echo 'Absolute output path required' >&2; exit 1;; esac
mkdir -p "$out"
docker image save mice-ocr-surya:0.14.7 | gzip > "$out/mice-ocr-surya-0.14.7.tar.gz"
tar -C "$root" -czf "$out/surya-models.tar.gz" surya/models surya/models.lock.json surya/requirements.lock surya/LICENSE surya/UPSTREAM-README.md
cd "$out"
sha256sum mice-ocr-surya-0.14.7.tar.gz surya-models.tar.gz > SHA256SUMS
