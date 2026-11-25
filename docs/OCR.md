# OCR providers

## Architecture

The existing `extraction.extract → ocr.complete → detection.detect` mail pipeline is unchanged.
Native extraction remains in `app.extraction`; OCR adapters only recognize raster pages.
`Setting[ocr]` stores `{enabled, provider}`. Default: RapidOCR. Each running OCR job
persists its configuration in its payload before processing its first attachment,
including on retry. There is no fallback, voting, or mixing of engines.
Disabling OCR affects new OCR jobs, not already running ones.
A failed/offline provider produces an explicit failure/partial result; other engines are never called.

## Surya (experimental; no LLM)

Surya **0.14.7**, torch **2.7.1**, transformers **4.53.3**; full transitive pins are
in `surya/requirements.lock`. This is the dedicated detection/recognition OCR API,
not the Surya 2.5 VLM/llama.cpp API used in the previous experiment.
Model releases: detection **2025_05_07**, recognition **2025_05_16**.
`surya/models.lock.json` pins SHA-256 for every shipped model asset.

### Licensing — review before commercial deployment or redistribution

The selected code tag is GPL-3.0-or-later (`surya/LICENSE`). Model weights are
CC-BY-NC-SA-4.0 according to the selected tag's README, with the publisher's stated
commercial waiver only for organizations below BOTH $2M revenue over the most
recent 12 months and $2M lifetime VC/angel funding, and not competing with Datalab API.
Do not assume this waiver covers your organization. Larger/commercial deployments
outside those terms need permission/commercial licensing from the publisher.
Separate Docker packaging does not remove license obligations. Preserve notices and
provide corresponding source as required when distributing the image. The source
README is preserved in `surya/UPSTREAM-README.md`; consult legal counsel for your usage.
Upstream reference: https://github.com/datalab-to/surya/tree/v0.14.7

### Build and start (online preparation)

```sh
python3 scripts/prepare_surya.py
docker compose --profile ocr-surya build ocr-surya
docker compose --profile ocr-surya up -d ocr-surya
```

No runtime download: all model paths are local; offline flags enabled; inference
subprocess denies socket syscalls. Container is unprivileged/read-only, without DB
credentials, on the existing internal OCR network. CPU is default. RAM cap 6 GiB,
2 CPU, one document at a time; adjust `MICE_SURYA_MEMORY`/`MICE_SURYA_CPUS` if needed.
Limits: manual upload 10 MiB, 200 pages, 25M raster pixels, isolated subprocess,
180 seconds Surya / 120 seconds other parsers (CPU limits are separate).
CPU and GPU dependency locks are separate (`requirements.cpu.lock` and
`requirements.gpu.lock`). The default image uses CPU-only torch. GPU requires NVIDIA Container Toolkit and compatible host driver:

```sh
docker compose -f compose.yaml -f compose.surya-gpu.yaml --profile ocr-surya up -d --build ocr-surya
```

### Offline export/import

```sh
sh scripts/export_surya.sh /absolute/path/ocr-export
# Transfer directory on approved removable media.
cd /absolute/path/ocr-export
sha256sum -c SHA256SUMS
gunzip -c mice-ocr-surya-0.14.7.tar.gz | docker load
# Optional model/source extraction into the checkout:
tar -xzf surya-models.tar.gz -C /absolute/path/Mail-Fire
cd /absolute/path/Mail-Fire
docker compose --profile ocr-surya up -d --no-build --pull never ocr-surya
```

Models are inside the exported image and additionally archived separately. Export
is not complete until the script succeeds; don't treat build context as a release.

## Settings and manual testing

Administrator-only `/settings/ocr/`: enable/disable, choose provider, check service
and local model availability, inspect package/model version and configured device.
Health checks are lightweight readiness checks, not an inference test; use manual
recognition to verify actual runtime/GPU readiness. Switching requires no restart.

Manual tests use the same `parser_client → parser_service → sandbox → extraction →
ocr.recognize` interface as mail. PNG/JPEG/TIFF/BMP/WebP/PDF; original is rasterized
in the existing sandbox, never embedded as active PDF/HTML. Multipage TIFF is supported.
Force PDF OCR ignores the text layer only for that request. Upload once, select a
different provider and recognize again without re-upload. Page selector displays
other original pages; text can be copied/downloaded locally. Confidence is the mean
of available block scores, not a calibrated cross-engine quality metric.

Temporary bytes are in a dedicated table, not mail/blob/training tables. Signed
15-minute tokens are owner-bound; expired reads are denied. Celery maintenance
purges expired rows every minute (requires beat/maintenance); requests also purge.
Parser temporary directories are removed after each call. No document contents or
filenames are written to parser logs. DB backups/WAL can retain deleted bytes under
normal database retention; apply your existing backup policy. Responses are no-store.

Run tests: `docker compose run --rm --no-deps web python manage.py test records pipeline identity policy_engine`.
