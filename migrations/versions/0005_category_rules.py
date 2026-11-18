"""Multiple detection rules for each user category; evolve draft catalog schema."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0005"
down_revision = "0004"


def upgrade():
    op.add_column("categories", sa.Column("match_mode", sa.String(8), nullable=False, server_default="any"))
    op.create_table(
        "category_rules",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("category_id", sa.String(64), sa.ForeignKey("categories.id", ondelete="CASCADE"), nullable=False),
        sa.Column("kind", sa.String(24), nullable=False),
        sa.Column("title", sa.String(160), nullable=False, server_default=""),
        sa.Column("enabled", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("risk", sa.Integer, nullable=False, server_default="70"),
        sa.Column("priority", sa.Integer, nullable=False, server_default="100"),
        sa.Column("config", JSONB, nullable=False),
        sa.CheckConstraint("risk >= 0 AND risk <= 100", name="ck_category_rule_risk"),
    )
    op.create_index("ix_category_rules_category_id", "category_rules", ["category_id"])
    # Convert draft PR #2 single-mode categories to their initial rule.
    op.execute("""
      INSERT INTO category_rules (id, category_id, kind, title, enabled, risk, config)
      SELECT gen_random_uuid()::text, id,
        CASE mode WHEN 'keywords' THEN 'keywords' WHEN 'reference' THEN 'reference' ELSE 'ml' END,
        'Первоначальное правило', true, 70,
        CASE mode
          WHEN 'keywords' THEN jsonb_build_object('phrases', keywords)
          WHEN 'reference' THEN jsonb_build_object('reference_ids', jsonb_build_array(reference_id), 'min_similarity', 0.8)
          ELSE '{}'::jsonb
        END
      FROM categories WHERE mode IN ('keywords', 'reference', 'ml') AND id LIKE 'custom-%'
    """)


def downgrade():
    op.drop_index("ix_category_rules_category_id", table_name="category_rules")
    op.drop_table("category_rules")
    op.drop_column("categories", "match_mode")
