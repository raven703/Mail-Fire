"""Unit coverage for explicit policy category OR/AND semantics."""

from app.processing import policy_matches


def _finding(category, risk=60):
    return {"category": category, "risk": risk}


def test_any_category_with_risk_40_and_one_finding():
    conditions = {
        "categories": ["RU_INN", "RU_SNILS", "CONFIDENTIAL"],
        "category_match": "any", "min_risk": 40, "min_count": 1,
    }
    assert policy_matches([_finding("RU_INN", 40)], conditions)
    assert not policy_matches([_finding("RU_INN", 39), _finding("CODE", 90)], conditions)


def test_all_categories_require_each_category_to_match_threshold():
    conditions = {
        "categories": ["RU_INN", "RU_SNILS", "CONFIDENTIAL"],
        "category_match": "all", "min_risk": 40, "min_count": 1,
    }
    assert not policy_matches([_finding("RU_INN", 90), _finding("RU_INN", 90)], conditions)
    assert not policy_matches([
        _finding("RU_INN"), _finding("RU_SNILS", 39), _finding("CONFIDENTIAL")
    ], conditions)
    assert len(policy_matches([
        _finding("RU_INN"), _finding("RU_SNILS"), _finding("CONFIDENTIAL")
    ], conditions)) == 3


def test_total_minimum_finding_count_separate_from_category_coverage():
    any_mode = {"categories": ["A", "B"], "category_match": "any", "min_risk": 40, "min_count": 2}
    assert not policy_matches([_finding("A")], any_mode)
    assert len(policy_matches([_finding("A"), _finding("A")], any_mode)) == 2

    all_mode = {**any_mode, "category_match": "all"}
    assert not policy_matches([_finding("A"), _finding("A")], all_mode)
    assert len(policy_matches([_finding("A"), _finding("B")], all_mode)) == 2


def test_empty_selection_and_old_policies_are_any_category():
    assert policy_matches([_finding("SECRET", 45)], {"min_risk": 40, "min_count": 1})
    assert policy_matches([_finding("SECRET", 45)], {"category_match": "any", "categories": []})
    assert not policy_matches([_finding("SECRET", 45)], {"category_match": "all", "categories": []})
