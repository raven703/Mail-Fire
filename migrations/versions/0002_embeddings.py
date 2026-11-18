"""Versioned semantic chunks in PostgreSQL, without modifying existing data."""

from alembic import op

revision = "0002"
down_revision = "0001"


def upgrade():
    op.execute("""CREATE TABLE semantic_chunks (
        id bigserial PRIMARY KEY, source_type text NOT NULL,
        source_id varchar(36) NOT NULL, chunk_index integer NOT NULL,
        text text NOT NULL, model text NOT NULL, embedding vector(384) NOT NULL,
        created_at timestamp NOT NULL DEFAULT now(),
        UNIQUE(source_type,source_id,chunk_index,model))""")
    op.execute("CREATE INDEX semantic_chunks_source ON semantic_chunks(source_type,source_id)")
    op.execute(
        "CREATE INDEX semantic_chunks_vector ON semantic_chunks USING hnsw (embedding vector_cosine_ops)"
    )


def downgrade():
    op.execute("DROP TABLE semantic_chunks")
