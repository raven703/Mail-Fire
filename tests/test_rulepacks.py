"""Rulepack contract and isolated-DB roundtrip. Never run DB tests on production."""
import copy
import json
import os
import uuid
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.rulepacks import Rulepack, load_pack

BASE = Path(__file__).resolve().parents[1] / "config" / "rulepacks" / "base_ru.json"


def test_base_rulepack_is_valid_and_explicitly_disabled():
    pack = load_pack(BASE)
    assert pack.schema_version == 1
    assert len(pack.categories) >= 5
    assert any("угроз" in c.name.lower() for c in pack.categories)
    assert len(pack.policies) >= 5
    assert all(not policy.enabled for policy in pack.policies)
    assert all(set(policy.categories) <= {c.id for c in pack.categories} for policy in pack.policies)
    assert all(category.match_mode in {"any", "all"} for category in pack.categories)


def test_rulepack_rejects_duplicates_and_unknown_attributes():
    base = load_pack(BASE).model_dump()
    duplicate = copy.deepcopy(base)
    duplicate["categories"].append(copy.deepcopy(duplicate["categories"][0]))
    with pytest.raises(ValidationError, match="Повторные"):
        Rulepack.model_validate(duplicate)
    unknown = copy.deepcopy(base)
    unknown["policies"][0]["arbitrary_behavior"] = "ALLOW_ALL"
    with pytest.raises(ValidationError):
        Rulepack.model_validate(unknown)


def test_invalid_rule_and_regex_rejected_before_writes():
    from app.rulepacks import _rule_validated
    from app.categories import safe_regex

    with pytest.raises(ValueError, match="Неизвестные поля"):
        _rule_validated({"kind": "keywords", "phrases": ["foo"], "external_command": "ls"})
    with pytest.raises(ValueError):
        safe_regex("(a+)+")


@pytest.mark.skipif(not os.getenv("MAILFIRE_TEST_DB"), reason="Only disposable PostgreSQL")
def test_rulepack_apply_export_and_explicit_update():
    from sqlalchemy import delete, select
    from app.db import transaction
    from app.models import Audit, Category, CategoryRule, Policy
    from app.rulepacks import apply_pack, export_pack, inspect_pack

    suffix = uuid.uuid4().hex[:12]
    category_id = "pack-test-" + suffix
    policy_name = "Synthetic rulepack " + suffix
    raw = {
        "schema_version": 1,
        "name": "synthetic-" + suffix,
        "categories": [{
            "id": category_id,
            "name": "Synthetic detector " + suffix,
            "group_name": "Tests",
            "active": True,
            "match_mode": "any",
            "rules": [{"kind": "keywords", "title": "Synth", "risk": 60,
                       "phrases": ["только синтетическая тестовая фраза"]}],
        }],
        "policies": [{
            "name": policy_name, "enabled": False,
            "categories": [category_id], "min_risk": 40
        }],
    }
    pack = Rulepack.model_validate(raw)
    try:
        with transaction() as session:
            plan = inspect_pack(session, pack)
            assert plan["categories"][0]["action"] == "create"
            assert plan["policies"][0]["action"] == "create"
            assert session.get(Category, category_id) is None
        with transaction() as session:
            result = apply_pack(session, pack, actor="rulepack-test")
            assert result == plan
        with transaction() as session:
            row = session.get(Category, category_id)
            assert row.mode == "custom" and row.active
            assert len(list(session.scalars(select(CategoryRule).where(CategoryRule.category_id == category_id)))) == 1
            policy = session.scalar(select(Policy).where(Policy.name == policy_name))
            assert not policy.enabled
            original_version = policy.version
            exported = export_pack(session, "fixture-export")
            assert any(c.id == category_id for c in exported.categories)
            assert any(p.name == policy_name for p in exported.policies)
            skipped = apply_pack(session, pack, actor="rulepack-test")
            assert skipped["categories"][0]["action"] == "skip"
            assert session.get(Policy, policy.id).version == original_version
        changed = pack.model_copy(deep=True)
        changed.categories[0].rules[0]["risk"] = 75
        with transaction() as session:
            updated = apply_pack(session, changed, actor="rulepack-test", update_existing=True)
            assert updated["categories"][0]["action"] == "update"
            assert updated["policies"][0]["action"] == "update"
            policy = session.scalar(select(Policy).where(Policy.name == policy_name))
            assert policy.version == original_version + 1
        with transaction() as session:
            rule = session.scalar(select(CategoryRule).where(CategoryRule.category_id == category_id))
            assert rule.risk == 75
    finally:
        with transaction() as session:
            session.execute(delete(Policy).where(Policy.name == policy_name))
            session.execute(delete(CategoryRule).where(CategoryRule.category_id == category_id))
            session.execute(delete(Category).where(Category.id == category_id))
            session.execute(delete(Audit).where(
                Audit.actor == "rulepack-test",
                Audit.details["pack"].astext == pack.name,
            ))


@pytest.mark.skipif(not os.getenv("MAILFIRE_TEST_DB"), reason="Only disposable PostgreSQL")
def test_invalid_pack_transaction_untouched():
    from sqlalchemy import select
    from app.db import transaction
    from app.models import Category
    from app.rulepacks import inspect_pack

    pack = load_pack(BASE).model_copy(deep=True)
    pack.categories[0].rules[0]["phrases"] = ["x"]  # too short
    with transaction() as session:
        before = session.scalar(select(Category.id).where(Category.id == pack.categories[0].id))
        with pytest.raises(Exception):
            inspect_pack(session, pack)
        after = session.scalar(select(Category.id).where(Category.id == pack.categories[0].id))
        assert before == after
