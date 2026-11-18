"""Initial PostgreSQL schema."""

from alembic import op

from app import models  # noqa: F401
from app.db import Base

revision = "0001"
down_revision = None


def upgrade():
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    Base.metadata.create_all(op.get_bind())
    op.execute("CREATE INDEX contents_fts ON contents USING gin (to_tsvector('simple', text))")


def downgrade():
    Base.metadata.drop_all(op.get_bind())
