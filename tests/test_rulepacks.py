"""Rulepack contract and isolated-DB roundtrip. Never run DB tests on production."""
import copy
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
    from app.categories import safe_regex
    from app.rulepacks import _rule_validated

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


@pytest.mark.skipif(not os.getenv("MAILFIRE_TEST_DB"), reason="Only disposable PostgreSQL")
def test_base_synthetic_texts_and_import_safety():
    from sqlalchemy import select

    from app.categories import custom_findings
    from app.models import Audit, Category, Policy
    from app.rulepacks import apply_pack, inspect_pack

    pack = load_pack(BASE)
    # Roll back every fixture, including audit; no persistent changes.
    from app.db import Session

    session = Session()
    try:
        before = list(session.scalars(select(Category.id)))
        inspect_pack(session, pack)
        assert list(session.scalars(select(Category.id))) == before
        pack.policies[0].enabled = True
        apply_pack(session, pack, actor="synthetic-safety")
        session.flush()
        policy = session.scalar(select(Policy).where(Policy.name == pack.policies[0].name))
        assert policy.enabled is False
        policy.conditions = {**policy.conditions, "future_setting": "preserved"}
        session.flush()
        apply_pack(session, pack, actor="synthetic-safety", update_existing=True)
        assert policy.conditions["future_setting"] == "preserved"
        foreign = pack.model_copy(deep=True)
        foreign.name = "different-owner"
        with pytest.raises(ValueError, match="другому набору"):
            inspect_pack(session, foreign, update_existing=True)
        for text, expected in [
            ("Синтетический пример: я тебя убью", "pack-threat-violence"),
            ("Синтетический пример: заложена бомба", "pack-threat-explosive"),
            ("Поступило сообщение о минировании", "pack-threat-explosive"),
            ("Сегодня обсуждаем прогулку в парке", None),
        ]:
            ids = {f["category"] for f in custom_findings(session, text)}
            assert expected in ids if expected else not ids
        # Literal keyword rules cannot distinguish reporting/quotation from intent.
        quoted = custom_findings(session, 'В статье приведена цитата «я тебя убью», это не угроза автора.')
        assert any(f["category"] == "pack-threat-violence" for f in quoted)
        assert session.scalar(select(Audit.id).where(Audit.actor == "synthetic-safety"))
    finally:
        session.rollback()
        session.close()


@pytest.mark.skipif(not os.getenv("MAILFIRE_TEST_DB"), reason="Only disposable PostgreSQL")
def test_rulepack_api_preview_apply_export_auth():
    from fastapi.testclient import TestClient

    from app.main import app

    suffix = uuid.uuid4().hex[:12]
    pack = {"schema_version": 1, "name": "api-" + suffix,
            "categories": [{"id": "pack-api-" + suffix, "name": "API synthetic " + suffix,
                            "group_name": "Tests", "rules": [{"kind": "keywords", "phrases": ["синтетическая фраза"]}]}]}
    with TestClient(app, base_url="https://testserver") as client:
        assert client.get("/api/rulepacks/export").status_code == 401
        login = client.post("/api/login", json={"username": "admin", "password": "synthetic-test-password-only"})
        headers = {"X-CSRF-Token": login.json()["csrf"]}
        body = {"pack": pack}
        assert client.post("/api/rulepacks/apply", json=body).status_code == 403
        preview = client.post("/api/rulepacks/preview", json=body, headers=headers)
        assert preview.status_code == 200, preview.text
        assert preview.json()["changes"]["categories"][0]["action"] == "create"
        assert client.post("/api/rulepacks/apply", json=body, headers=headers).status_code == 200
        again = client.post("/api/rulepacks/apply", json=body, headers=headers)
        assert again.json()["changes"]["categories"][0]["action"] == "skip"
        exported = client.get("/api/rulepacks/export")
        assert exported.status_code == 200, exported.text
        assert any(c["id"] == pack["categories"][0]["id"] for c in exported.json()["categories"])
