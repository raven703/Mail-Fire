"""Initial PostgreSQL schema."""

from alembic import op

from app import models  # noqa: F401
from app.db import Base

revision = "0001"
down_revision = None


def upgrade():
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    # Later catalog tables must be introduced by their versioned migrations,
    # not accidentally created from today's ORM metadata on a fresh install.
    import sqlalchemy as sa

    historical = sa.MetaData()
    for table in Base.metadata.sorted_tables:
        if table.name not in {"categories", "category_rules"}:
            table.to_metadata(historical)
    training = historical.tables["training_examples"]
    column = training.c.source_incident_id
    for constraint in list(training.constraints):
        if column in list(constraint.columns):
            training.constraints.remove(constraint)
    training._columns.remove(column)
    historical.create_all(op.get_bind())
    op.execute("CREATE INDEX contents_fts ON contents USING gin (to_tsvector('simple', text))")


def downgrade():
    Base.metadata.drop_all(op.get_bind())
