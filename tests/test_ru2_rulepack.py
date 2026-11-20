"""RU2 is valid, reachable by positive examples, and safe to import disabled."""
from pathlib import Path

from app.rulepacks import _rule_validated, load_pack
from app.text_match import search, tokens


def test_ru2_rules_are_reachable_and_policies_disabled():
    pack = load_pack(Path(__file__).resolve().parents[1] / "config/rulepacks/ru2_morph_weighted_rules.json")
    assert len(pack.categories) == len(pack.policies) == 12
    assert all(not policy.enabled for policy in pack.policies)
    ids = {category.id for category in pack.categories}
    assert all(set(policy.categories) <= ids for policy in pack.policies)
    for category in pack.categories:
        for rule in category.rules:
            _rule_validated(rule)
            if rule.get("match_type") == "flexible":
                terms = rule["terms"]
                assert rule["min_score"] <= sum(term["weight"] for term in terms)
                sample = " ".join(term["text"] for term in terms)
                assert len(tokens(sample, True)) <= rule["window"]
                assert search(sample, mode="flexible", terms=terms,
                              min_score=rule["min_score"], window=rule["window"],
                              ordered=rule["ordered"]), rule["title"]