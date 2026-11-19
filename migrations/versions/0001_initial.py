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
    # Fields added by later migrations must not exist at revision 0001.
    for name in ["archived"]:
        historical.tables["policies"]._columns.remove(historical.tables["policies"].c[name])
    for name in ["message_id", "policy_hits"]:
        column = historical.tables["incidents"].c[name]
        for foreign_key in list(column.foreign_keys):
            historical.tables["incidents"].foreign_keys.discard(foreign_key)
        for constraint in list(historical.tables["incidents"].constraints):
            if any(c is column for c in constraint.columns):
                historical.tables["incidents"].constraints.remove(constraint)
        for index in list(historical.tables["incidents"].indexes):
            if any(c is column for c in index.columns):
                historical.tables["incidents"].indexes.remove(index)
        historical.tables["incidents"]._columns.remove(column)
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
