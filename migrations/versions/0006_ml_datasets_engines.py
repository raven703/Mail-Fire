"""Dataset provenance and configurable local ML classifier engines."""

import sqlalchemy as sa
from alembic import op

revision = "0006"
down_revision = "0005"


def upgrade():
    op.create_table(
        "ml_datasets",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("source", sa.String(120), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("fingerprint", sa.String(64), nullable=False),
        sa.Column("example_count", sa.Integer(), nullable=False),
    )
    op.create_index("ix_ml_datasets_created_at", "ml_datasets", ["created_at"])
    op.add_column("training_examples", sa.Column("dataset_id", sa.String(36), nullable=True))
    op.add_column("training_examples", sa.Column("source", sa.String(80), nullable=False, server_default="manual"))
    op.add_column("training_examples", sa.Column("reviewed_by", sa.String(36), nullable=True))
    op.create_foreign_key("fk_ml_examples_dataset", "training_examples", "ml_datasets", ["dataset_id"], ["id"], ondelete="SET NULL")
    op.create_foreign_key("fk_ml_examples_reviewer", "training_examples", "accounts", ["reviewed_by"], ["id"], ondelete="SET NULL")
    op.create_index("ix_training_examples_dataset_id", "training_examples", ["dataset_id"])
    op.add_column("ml_models", sa.Column("engine", sa.String(24), nullable=False, server_default="tfidf"))
    op.add_column("ml_models", sa.Column("category_id", sa.String(64), nullable=True))
    op.add_column("ml_models", sa.Column("dataset_id", sa.String(36), nullable=True))
    op.create_foreign_key("fk_ml_models_category", "ml_models", "categories", ["category_id"], ["id"], ondelete="SET NULL")
    op.create_foreign_key("fk_ml_models_dataset", "ml_models", "ml_datasets", ["dataset_id"], ["id"], ondelete="SET NULL")
    op.create_index("ix_ml_models_category_id", "ml_models", ["category_id"])
    # Existing TF-IDF model remains valid and publishable as the global classifier.


def downgrade():
    op.drop_index("ix_ml_models_category_id", table_name="ml_models")
    op.drop_constraint("fk_ml_models_dataset", "ml_models", type_="foreignkey")
    op.drop_constraint("fk_ml_models_category", "ml_models", type_="foreignkey")
    for col in ["dataset_id", "category_id", "engine"]:
        op.drop_column("ml_models", col)
    op.drop_index("ix_training_examples_dataset_id", table_name="training_examples")
    op.drop_constraint("fk_ml_examples_reviewer", "training_examples", type_="foreignkey")
    op.drop_constraint("fk_ml_examples_dataset", "training_examples", type_="foreignkey")
    for col in ["reviewed_by", "source", "dataset_id"]:
        op.drop_column("training_examples", col)
    op.drop_index("ix_ml_datasets_created_at", table_name="ml_datasets")
    op.drop_table("ml_datasets")
