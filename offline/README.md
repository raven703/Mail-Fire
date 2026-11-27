# MICE offline Linux amd64

Reference host: Docker Engine 29.6.1, Compose plugin 5.3.0.

Build on the trusted staging host: `python3 offline/build_bundle.py` from the
repository root. The builder intentionally refuses an existing staging directory.
It reads the running web application's database in a repeatable-read, read-only
transaction. It does not stop, recreate or write to production services.

Transfer `dist/MICE-offline-linux-amd64.tar.gz` and its `.sha256` file. Check the
archive checksum, extract it, enter the extracted directory and run `./install.sh`.
Docker, Compose, POSIX shell, coreutils and tar must already be available. Allow
at least 35 GB free disk and sufficient RAM for concurrent CPU model inference.
Open http://127.0.0.1:18080, user `admin`. The generated password is in the private
`.env` file. For remote access use an SSH tunnel or a separately configured TLS
reverse proxy. This package does not configure public HTTP access.

`./start.sh`, `./stop.sh` and `./verify.sh` operate only on the installation's
randomly generated `mice-offline-*` project. Stop preserves all installation data.
An interrupted installation may need manual repair: do not delete `.env` and
regenerate credentials for existing database volumes. No Docker prune is used.

All application networks are internal. Only nginx also joins an edge bridge,
because Docker does not publish host ports for internal-only networks. Thus this
is application-worker egress isolation, not an air-gapped Docker daemon. A full
host-disconnected, empty-daemon installation must be tested separately.

The bundle contains categories, live category rules, policies, approved current
settings, immutable inference artifacts if present, trained model artifacts if
present, and separately discovered on-disk RuBERT/SetFit models. No users/password
hashes, messages, attachments, incidents, analysis output, audit, datasets,
training reports, configuration backups or migration history are exported.
UI preferences retain their opaque user keys; old user accounts are not restored.
External integrations cannot work offline and require new target-side credentials.
Models present only as files are included but are not automatically published as
active DB models. Existing active detector switches are preserved.

Verification checks Django configuration, health, empty operational tables,
Horizon CPU logits, RuBERT/SetFit local encoding, and RapidOCR initialization.
These are smoke checks, not OCR accuracy, full detector coverage, security audit,
or end-to-end mail processing certification. Surya image/models are included but
Surya recognition quality is not certified by these checks.

Build artifacts and exported customer configuration stay out of Git. Review
configuration and model provenance before distributing to another organization.