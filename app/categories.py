"""Category catalog helpers used by policies, detectors and ML.

Category IDs are server-assigned. A new ML category alone does not detect text.
"""
from sqlalchemy import select

from app.models import Category


def available_categories(session, ids, *, allow_label=True):
    values = set(ids)
    if not values:
        return True
    rows = session.scalars(select(Category).where(Category.id.in_(values), Category.active.is_(True)))
    found = {r.id for r in rows if allow_label or r.mode != "label"}
    return found == values


def keyword_findings(session, text):
    """Literal phrases, not arbitrary regexes; bounded to avoid catastrophic backtracking."""
    from app.advanced_detectors import finding

    result = []
    low = text.lower()
    rows = session.scalars(select(Category).where(Category.active.is_(True), Category.mode == "keywords"))
    for category in rows:
        for word in category.keywords[:30]:
            needle = word.strip().lower()
            if len(needle) < 3:
                continue
            start = low.find(needle)
            if start < 0:
                continue
            result.append(
                finding(
                    category.id,
                    "custom-keywords",
                    text[max(0, start - 50): min(len(text), start + len(needle) + 50)],
                    risk=70,
                    reason="Совпадение с ключевой фразой пользовательской категории",
                )
            )
            if len(result) >= 200:
                return result
    return result


def reference_findings(session, reference_id, excerpt, *, similarity=None):
    """Map a linked reference match onto user-defined categories."""
    from app.advanced_detectors import finding

    rows = session.scalars(
        select(Category).where(
            Category.active.is_(True),
            Category.mode == "reference",
            Category.reference_id == reference_id,
        )
    )
    return [
        finding(
            category.id,
            "custom-reference",
            excerpt,
            risk=75,
            reason="Совпадение с привязанным эталонным документом",
            similarity=similarity,
        )
        for category in rows
    ]
