# MICE: signed offline Docker releases (MVP)

This is a **first-stage offline delivery mechanism**, not a verified production-grade unattended upgrader.
It does not change the development `compose.yaml`. The target must already have Docker Engine,
Docker Compose v2, Bash, OpenSSL and sha256sum, on a compatible CPU architecture.

## Build on networked release machine

Use the release commit on a trusted builder, with all build-time OCR/embedding downloads available.
Keep the signing **private** key outside the Git repository and release archive; install its public
counterpart independently on every offline machine.

```sh
openssl genpkey -algorithm ed25519 -out release-private.pem
openssl pkey -in release-private.pem -pubout -out release-public.pem
# NOTE: the supplied bash scripts use openssl dgst -sha256 which requires an RSA/ECDSA key,
# not Ed25519. For this MVP generate an RSA key instead:
openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:3072 -out release-private.pem
openssl pkey -in release-private.pem -pubout -out release-public.pem
bash scripts/airgap/build.sh 0.1.0 release-private.pem ./dist
```

Package includes `mice/backend`, `mice/web`, pgvector PostgreSQL and optional ClamAV
images via `docker save`, along with version, commit, Compose and SHA-256 manifest.
Do not distribute `release-private.pem`. Verify available disk space (image bundle +
DB backup + PostgreSQL volume).

## Offline host

Copy the tarball and detached signature through your approved transfer process.
Copy the trusted public key via a **separate trusted provisioning channel**.
Install in a dedicated application directory where `.env` already contains local
passwords and runtime settings. Copy `scripts/airgap/install.sh` from reviewed
source, not from untrusted removable media. On a new machine initialize Compose
secrets and review service exposure and TLS before use.

```sh
bash scripts/airgap/install.sh /media/mice-release-0.1.0.tar \
  /media/mice-release-0.1.0.tar.sig /etc/mice/release-public.pem
```

The installer verifies the detached signature **before extraction**, then verifies payload hashes.
No `docker pull`, source build, PyPI or model download is performed on the offline host.
The release Compose uses `pull_policy: never` and `--pull never`.

### Important operational constraints

* PostgreSQL data and ML artifacts stored inside its persistent volume are not replaced.
  User policies, categories, reference documents and models remain in that database.
  Local `.env` is not overwritten. A backup of `.env` and `pg_dump -Fc` is taken for
  upgrades while DB is running; backup files contain sensitive data and must be encrypted/
  retained under local security policy. For first-time deployments the database is empty,
  and the admin must provision/bootstrap it as a separate, explicitly approved step.
* The release `migrate` service runs `alembic upgrade head` **without bootstrap**.
* Schema migration may be irreversible. The installer **does not** automatically restore
  DB data on failure, because this would destroy writes unless services are fully
  quiesced. Recovery procedure: stop the stack, restore the captured database into a
  clean compatible PostgreSQL instance, restore old Compose and version, restart the
  previous preloaded image set, and validate app state. Test recovery before production.
* This MVP does not bundle a neural SetFit image or external model snapshots unless
  already included in the default backend Docker image. It does not update ClamAV
  signatures offline. These require separate signed, versioned releases.
* Do not run concurrent installers. Take a VM/disk snapshot before a major database
  upgrade. PostgreSQL **major** upgrade is not covered; the Docker image remains pg17.
* Current `pgvector/pgvector:pg17` and `clamav/clamav:stable` tags are saved with
  the package and their content hashes protected by its signature. Pin upstream
  digests for reproducible builds in the next iteration.
* Preserve mail/ingest sources outside the database and verify acceptance/latency
  on a staging clone with outbound network blocked before deploying in production.

## Staging validation checklist

Verify signature rejection (tamper with bundle), corrupted archive rejection, fresh
install, upgrade with actual protected data, forced migration failure, stop/recovery,
no network routes, image/platform compatibility, and negative tests for insufficient
storage or a stopped database. **No such live isolated-host test is claimed by this PR.**
