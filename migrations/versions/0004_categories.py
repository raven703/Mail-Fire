"""Unified detector/ML category catalog and incident feedback provenance."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0004"
down_revision = "0003"

BUILTIN = [
    ("EMAIL", "Адрес электронной почты", "Персональные данные"),
    ("PHONE", "Телефон", "Персональные данные"),
    ("INN", "ИНН (правило)", "Персональные данные"),
    ("RU_INN", "ИНН (Presidio)", "Персональные данные"),
    ("RU_SNILS", "СНИЛС", "Персональные данные"),
    ("RU_PASSPORT", "Паспорт РФ", "Персональные данные"),
    ("RU_PHONE", "Телефон (Presidio)", "Персональные данные"),
    ("SECRET", "Пароли и токены", "Секреты"),
    ("PRIVATE_KEY", "Закрытый ключ", "Секреты"),
    ("CONFIDENTIAL", "Коммерческая тайна", "Конфиденциальные данные"),
    ("PROMPT_INJECTION", "Попытка изменить инструкции", "Безопасность"),
    ("CODE", "Исходный код", "Исходный код"),
    ("SUSPICIOUS_COMMAND", "Опасные команды", "Безопасность"),
    ("YARA", "YARA-сигнатура", "Безопасность"),
    ("OFFICE_MACRO", "Опасный макрос Office", "Безопасность"),
    ("MALWARE", "Вредоносный файл ClamAV", "Безопасность"),
    ("REFERENCE_DOCUMENT", "Совпадение с эталоном", "Документы"),
    ("SEMANTIC_REFERENCE", "Семантическое сходство", "Документы"),
    ("NORMAL", "Безопасный материал", "ML-разметка"),
]


def upgrade():
    op.create_table(
        "categories",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("name", sa.String(160), nullable=False, unique=True),
        sa.Column("group_name", sa.String(120), nullable=False),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("mode", sa.String(24), nullable=False),
        sa.Column("active", sa.Boolean, nullable=False),
        sa.Column("keywords", JSONB, nullable=False),
        sa.Column(
            "reference_id", sa.String(36), sa.ForeignKey("references.id", ondelete="SET NULL"), nullable=True
        ),
    )
    categories = sa.table(
        "categories",
        sa.column("id", sa.String),
        sa.column("name", sa.String),
        sa.column("group_name", sa.String),
        sa.column("description", sa.Text),
        sa.column("mode", sa.String),
        sa.column("active", sa.Boolean),
        sa.column("keywords", JSONB),
        sa.column("reference_id", sa.String),
    )
    op.bulk_insert(
        categories,
        [
            dict(
                id=code,
                name=name,
                group_name=group,
                description="",
                mode=("label" if code == "NORMAL" else "builtin"),
                active=True,
                keywords=[],
                reference_id=None,
            )
            for code, name, group in BUILTIN
        ],
    )
    op.add_column("training_examples", sa.Column("source_incident_id", sa.String(36), nullable=True))
    op.create_foreign_key(
        "fk_training_examples_source_incident",
        "training_examples",
        "incidents",
        ["source_incident_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_unique_constraint("uq_training_example_incident", "training_examples", ["source_incident_id"])


def downgrade():
    op.drop_constraint("uq_training_example_incident", "training_examples", type_="unique")
    op.drop_constraint("fk_training_examples_source_incident", "training_examples", type_="foreignkey")
    op.drop_column("training_examples", "source_incident_id")
    op.drop_table("categories")
