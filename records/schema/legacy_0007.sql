-- Frozen source schema at 0e303b1; no runtime SQLAlchemy dependency.

CREATE EXTENSION IF NOT EXISTS vector;

CREATE EXTENSION IF NOT EXISTS pg_trgm;


CREATE TABLE accounts (
	username VARCHAR NOT NULL, 
	password_hash VARCHAR NOT NULL, 
	role VARCHAR NOT NULL, 
	originals BOOLEAN NOT NULL, 
	enabled BOOLEAN NOT NULL, 
	id VARCHAR(36) NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (username)
)

;

CREATE INDEX ix_accounts_created_at ON accounts (created_at);


CREATE TABLE audit (
	actor VARCHAR NOT NULL, 
	action VARCHAR NOT NULL, 
	target VARCHAR NOT NULL, 
	details JSONB NOT NULL, 
	id VARCHAR(36) NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id)
)

;

CREATE INDEX ix_audit_created_at ON audit (created_at);


CREATE TABLE blobs (
	sha VARCHAR(64) NOT NULL, 
	data BYTEA NOT NULL, 
	size INTEGER NOT NULL, 
	PRIMARY KEY (sha)
)

;


CREATE TABLE contents (
	normalized_sha VARCHAR(64) NOT NULL, 
	text TEXT NOT NULL, 
	analysis JSONB NOT NULL, 
	version VARCHAR NOT NULL, 
	id VARCHAR(36) NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (normalized_sha)
)

;

CREATE INDEX ix_contents_created_at ON contents (created_at);


CREATE TABLE diagnostics (
	service VARCHAR NOT NULL, 
	level VARCHAR NOT NULL, 
	event VARCHAR NOT NULL, 
	details JSONB NOT NULL, 
	id VARCHAR(36) NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id)
)

;

CREATE INDEX ix_diagnostics_created_at ON diagnostics (created_at);


CREATE TABLE identities (
	name VARCHAR NOT NULL, 
	department VARCHAR NOT NULL, 
	id VARCHAR(36) NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id)
)

;

CREATE INDEX ix_identities_created_at ON identities (created_at);


CREATE TABLE jobs (
	kind VARCHAR NOT NULL, 
	payload JSONB NOT NULL, 
	status VARCHAR NOT NULL, 
	attempts INTEGER NOT NULL, 
	priority INTEGER NOT NULL, 
	available_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	lease_until TIMESTAMP WITHOUT TIME ZONE, 
	owner VARCHAR, 
	error TEXT, 
	finished_at TIMESTAMP WITHOUT TIME ZONE, 
	id VARCHAR(36) NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id)
)

;

CREATE INDEX ix_jobs_created_at ON jobs (created_at);

CREATE INDEX ix_jobs_kind ON jobs (kind);

CREATE INDEX ix_jobs_status ON jobs (status);

CREATE INDEX jobs_claim ON jobs (status, available_at, priority);


CREATE TABLE metrics (
	service VARCHAR NOT NULL, 
	values JSONB NOT NULL, 
	id VARCHAR(36) NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id)
)

;

CREATE INDEX ix_metrics_created_at ON metrics (created_at);


CREATE TABLE ml_datasets (
	name VARCHAR(160) NOT NULL, 
	source VARCHAR(120) NOT NULL, 
	description TEXT NOT NULL, 
	version INTEGER NOT NULL, 
	status VARCHAR(20) NOT NULL, 
	fingerprint VARCHAR(64) NOT NULL, 
	example_count INTEGER NOT NULL, 
	id VARCHAR(36) NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id)
)

;

CREATE INDEX ix_ml_datasets_created_at ON ml_datasets (created_at);


CREATE TABLE policies (
	name VARCHAR NOT NULL, 
	enabled BOOLEAN NOT NULL, 
	shadow BOOLEAN NOT NULL, 
	version INTEGER NOT NULL, 
	priority INTEGER NOT NULL, 
	conditions JSONB NOT NULL, 
	archived BOOLEAN NOT NULL, 
	id VARCHAR(36) NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id)
)

;

CREATE INDEX ix_policies_created_at ON policies (created_at);


CREATE TABLE settings (
	key VARCHAR NOT NULL, 
	value JSONB NOT NULL, 
	PRIMARY KEY (key)
)

;


CREATE TABLE addresses (
	email VARCHAR NOT NULL, 
	identity_id VARCHAR(36), 
	kind VARCHAR NOT NULL, 
	id VARCHAR(36) NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (email), 
	FOREIGN KEY(identity_id) REFERENCES identities (id)
)

;

CREATE INDEX ix_addresses_created_at ON addresses (created_at);


CREATE TABLE messages (
	original_sha VARCHAR(64) NOT NULL, 
	format VARCHAR NOT NULL, 
	subject TEXT NOT NULL, 
	sender VARCHAR NOT NULL, 
	recipients JSONB NOT NULL, 
	headers JSONB NOT NULL, 
	content_id VARCHAR(36), 
	status VARCHAR NOT NULL, 
	error TEXT, 
	legal_hold BOOLEAN NOT NULL, 
	id VARCHAR(36) NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (original_sha), 
	FOREIGN KEY(original_sha) REFERENCES blobs (sha), 
	FOREIGN KEY(content_id) REFERENCES contents (id)
)

;

CREATE INDEX ix_messages_created_at ON messages (created_at);

CREATE INDEX ix_messages_status ON messages (status);


CREATE TABLE "references" (
	name VARCHAR NOT NULL, 
	blob_sha VARCHAR(64) NOT NULL, 
	text TEXT NOT NULL, 
	fingerprint JSONB NOT NULL, 
	id VARCHAR(36) NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(blob_sha) REFERENCES blobs (sha)
)

;

CREATE INDEX ix_references_created_at ON "references" (created_at);


CREATE TABLE sessions (
	token_hash VARCHAR(64) NOT NULL, 
	account_id VARCHAR(36) NOT NULL, 
	expires_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (token_hash), 
	FOREIGN KEY(account_id) REFERENCES accounts (id)
)

;


CREATE TABLE attachments (
	message_id VARCHAR(36) NOT NULL, 
	blob_sha VARCHAR(64) NOT NULL, 
	name TEXT NOT NULL, 
	mime VARCHAR NOT NULL, 
	status VARCHAR NOT NULL, 
	text TEXT NOT NULL, 
	details JSONB NOT NULL, 
	id VARCHAR(36) NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(message_id) REFERENCES messages (id), 
	FOREIGN KEY(blob_sha) REFERENCES blobs (sha)
)

;

CREATE INDEX ix_attachments_created_at ON attachments (created_at);

CREATE INDEX ix_attachments_message_id ON attachments (message_id);


CREATE TABLE categories (
	id VARCHAR(64) NOT NULL, 
	name VARCHAR(160) NOT NULL, 
	group_name VARCHAR(120) NOT NULL, 
	description TEXT NOT NULL, 
	mode VARCHAR(24) NOT NULL, 
	match_mode VARCHAR(8) NOT NULL, 
	active BOOLEAN NOT NULL, 
	keywords JSONB NOT NULL, 
	reference_id VARCHAR(36), 
	PRIMARY KEY (id), 
	UNIQUE (name), 
	FOREIGN KEY(reference_id) REFERENCES "references" (id) ON DELETE SET NULL
)

;


CREATE TABLE imports (
	source_key TEXT NOT NULL, 
	name TEXT NOT NULL, 
	status VARCHAR NOT NULL, 
	message_id VARCHAR(36), 
	error TEXT, 
	duplicate BOOLEAN NOT NULL, 
	id VARCHAR(36) NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (source_key), 
	FOREIGN KEY(message_id) REFERENCES messages (id)
)

;

CREATE INDEX ix_imports_created_at ON imports (created_at);


CREATE TABLE mail_events (
	message_id VARCHAR(36) NOT NULL, 
	source VARCHAR NOT NULL, 
	source_key TEXT NOT NULL, 
	direction VARCHAR NOT NULL, 
	envelope JSONB NOT NULL, 
	id VARCHAR(36) NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(message_id) REFERENCES messages (id), 
	UNIQUE (source_key)
)

;

CREATE INDEX ix_mail_events_created_at ON mail_events (created_at);

CREATE INDEX ix_mail_events_message_id ON mail_events (message_id);


CREATE TABLE category_rules (
	category_id VARCHAR(64) NOT NULL, 
	kind VARCHAR(24) NOT NULL, 
	title VARCHAR(160) NOT NULL, 
	enabled BOOLEAN NOT NULL, 
	risk INTEGER NOT NULL, 
	priority INTEGER NOT NULL, 
	config JSONB NOT NULL, 
	id VARCHAR(36) NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(category_id) REFERENCES categories (id) ON DELETE CASCADE
)

;

CREATE INDEX ix_category_rules_category_id ON category_rules (category_id);

CREATE INDEX ix_category_rules_created_at ON category_rules (created_at);


CREATE TABLE incidents (
	event_id VARCHAR(36) NOT NULL, 
	message_id VARCHAR(36) NOT NULL, 
	policy_id VARCHAR(36), 
	policy_hits JSONB NOT NULL, 
	status VARCHAR NOT NULL, 
	risk INTEGER NOT NULL, 
	findings JSONB NOT NULL, 
	assignee VARCHAR(36), 
	id VARCHAR(36) NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(event_id) REFERENCES mail_events (id), 
	FOREIGN KEY(message_id) REFERENCES messages (id), 
	FOREIGN KEY(policy_id) REFERENCES policies (id), 
	FOREIGN KEY(assignee) REFERENCES accounts (id)
)

;

CREATE INDEX ix_incidents_created_at ON incidents (created_at);

CREATE UNIQUE INDEX ix_incidents_message_id ON incidents (message_id);


CREATE TABLE ml_models (
	engine VARCHAR(24) NOT NULL, 
	category_id VARCHAR(64), 
	dataset_id VARCHAR(36), 
	name VARCHAR NOT NULL, 
	artifact BYTEA NOT NULL, 
	metrics JSONB NOT NULL, 
	active BOOLEAN NOT NULL, 
	eligible BOOLEAN NOT NULL, 
	id VARCHAR(36) NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(category_id) REFERENCES categories (id) ON DELETE SET NULL, 
	FOREIGN KEY(dataset_id) REFERENCES ml_datasets (id) ON DELETE SET NULL
)

;

CREATE INDEX ix_ml_models_category_id ON ml_models (category_id);

CREATE INDEX ix_ml_models_created_at ON ml_models (created_at);


CREATE TABLE comments (
	incident_id VARCHAR(36) NOT NULL, 
	account_id VARCHAR(36) NOT NULL, 
	text TEXT NOT NULL, 
	id VARCHAR(36) NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(incident_id) REFERENCES incidents (id), 
	FOREIGN KEY(account_id) REFERENCES accounts (id)
)

;

CREATE INDEX ix_comments_created_at ON comments (created_at);


CREATE TABLE outbox (
	incident_id VARCHAR(36) NOT NULL, 
	destination VARCHAR NOT NULL, 
	payload JSONB NOT NULL, 
	status VARCHAR NOT NULL, 
	attempts INTEGER NOT NULL, 
	available_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	error VARCHAR, 
	id VARCHAR(36) NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(incident_id) REFERENCES incidents (id)
)

;

CREATE INDEX ix_outbox_created_at ON outbox (created_at);


CREATE TABLE training_examples (
	dataset_id VARCHAR(36), 
	source VARCHAR(80) NOT NULL, 
	reviewed_by VARCHAR(36), 
	source_incident_id VARCHAR(36), 
	text TEXT NOT NULL, 
	group_sha VARCHAR(64) NOT NULL, 
	labels JSONB NOT NULL, 
	approved BOOLEAN NOT NULL, 
	id VARCHAR(36) NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(dataset_id) REFERENCES ml_datasets (id) ON DELETE SET NULL, 
	FOREIGN KEY(reviewed_by) REFERENCES accounts (id) ON DELETE SET NULL, 
	UNIQUE (source_incident_id), 
	FOREIGN KEY(source_incident_id) REFERENCES incidents (id) ON DELETE SET NULL
)

;

CREATE INDEX ix_training_examples_created_at ON training_examples (created_at);

CREATE INDEX ix_training_examples_dataset_id ON training_examples (dataset_id);

CREATE INDEX ix_training_examples_group_sha ON training_examples (group_sha);

CREATE INDEX contents_fts ON contents USING gin (to_tsvector('simple', text));

ALTER TABLE category_rules ADD CONSTRAINT ck_category_rule_risk CHECK (risk >= 0 AND risk <= 100);

CREATE TABLE semantic_chunks (id bigserial PRIMARY KEY, source_type text NOT NULL, source_id varchar(36) NOT NULL, chunk_index integer NOT NULL, text text NOT NULL, model text NOT NULL, embedding vector(384) NOT NULL, created_at timestamp NOT NULL DEFAULT now(), UNIQUE(source_type,source_id,chunk_index,model));

CREATE INDEX semantic_chunks_source ON semantic_chunks(source_type,source_id);

CREATE INDEX semantic_chunks_vector ON semantic_chunks USING hnsw (embedding vector_cosine_ops);

CREATE INDEX ix_messages_subject_trgm ON messages USING gin (subject gin_trgm_ops);

CREATE INDEX ix_messages_sender_trgm ON messages USING gin (sender gin_trgm_ops);

CREATE INDEX ix_contents_text_trgm ON contents USING gin (text gin_trgm_ops);

CREATE INDEX ix_attachments_name_trgm ON attachments USING gin (name gin_trgm_ops);

CREATE INDEX ix_messages_recipients_trgm ON messages USING gin ((recipients::varchar) gin_trgm_ops);

CREATE INDEX ix_incidents_event_risk ON incidents(event_id,risk);

CREATE INDEX ix_incidents_status_created ON incidents(status,created_at);

CREATE INDEX ix_mail_events_message_source ON mail_events(message_id,source,direction);
