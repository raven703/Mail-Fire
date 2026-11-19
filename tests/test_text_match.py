"""Pure CPU tests for configurable word, morphology and weighted matching."""
from app.text_match import norm, search


def test_legacy_substring_still_matches_inside_word():
    assert search("бомбарда", phrases=["бомба"])


def test_whole_word_rejects_substring_and_handles_case():
    assert not search("бомбарда", mode="word", phrases=["бомба"])
    assert search("Это БОМБА.", mode="word", phrases=["бомба"])


def test_russian_inflection_and_normalized_yo():
    assert search("Конфиденциальные документы", mode="morphology",
                  phrases=["конфиденциальный документ"])
    assert search("Все еще идет анализ", mode="word", phrases=["еще"])
    assert norm("Ёж", False) == "еж"


def test_flexible_weighted_window_and_required_terms():
    terms = [
        {"text": "передать", "weight": 2, "required": False},
        {"text": "документ", "weight": 1, "required": True},
        {"text": "конкурент", "weight": 4, "required": True},
    ]
    matches = search("передать документы непосредственным конкурентам", mode="flexible",
                     terms=terms, window=8, min_score=5)
    assert matches and matches[0][2] >= 5
    assert not search("передать документы конкурентам", mode="flexible", terms=terms,
                      window=2, min_score=7)
    assert not search("передать документы", mode="flexible", terms=terms,
                      window=8, min_score=1)
    assert not search("конкурентам передать документы", mode="flexible", terms=terms,
                      window=8, min_score=5, ordered=True)


def test_once_per_term_with_repeated_words():
    terms = [{"text": "бомба", "weight": 4, "required": True}]
    hit = search("бомба бомба бомба", mode="flexible", terms=terms, min_score=4)
    assert hit and hit[0][2] == 4
    assert not search("бомба бомба бомба", mode="flexible", terms=terms, min_score=5)


def test_exclusion_and_bounded_hits():
    assert not search("В инструкции сказано: бомба", phrases=["бомба"],
                      exclude_phrases=["В инструкции"])
    terms = [{"text": "документ", "weight": 1, "required": False}]
    assert len(search(" ".join(["документ"]*100), mode="flexible",
                      terms=terms, min_score=1)) <= 10
