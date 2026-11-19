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
        if table.name not in {"categories", "category_rules", "ml_datasets"}:
            table.to_metadata(historical)
    training = historical.tables["training_examples"]
    for table, names in [
        (training, ["source_incident_id", "dataset_id", "source", "reviewed_by"]),
        (historical.tables["ml_models"], ["engine", "category_id", "dataset_id"]),
    ]:
        for name in names:
            column = table.c[name]
            for foreign_key in list(column.foreign_keys):
                table.foreign_keys.discard(foreign_key)
            for constraint in list(table.constraints):
                if any(c is column for c in constraint.columns):
                    table.constraints.remove(constraint)
            for index in list(table.indexes):
                if any(c is column for c in index.columns):
                    table.indexes.remove(index)
            table._columns.remove(column)
    historical.create_all(op.get_bind())
    op.execute("CREATE INDEX contents_fts ON contents USING gin (to_tsvector('simple', text))")


def downgrade():
    Base.metadata.drop_all(op.get_bind())
