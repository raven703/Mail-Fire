"""Bounded CPU-only Russian-aware keyword and flexible phrase matcher.

Default literal matching is kept for imported rulepacks. Morphology uses
Razdel tokenization and pymorphy3 dictionaries, without downloaded model
weights. Each configured term scores at most once per window.
"""
import re
from bisect import bisect_left
from functools import lru_cache
from razdel import tokenize

WORD = re.compile(r"[^\W_]+", re.UNICODE)
@lru_cache(maxsize=8192)
def norm(word: str, morph: bool = False) -> str:
    word = word.casefold().replace("ё", "е")
    if not morph or not re.search(r"[а-я]", word):
        return word
    return _morph().parse(word)[0].normal_form.replace("ё", "е")


@lru_cache(maxsize=1)
def _morph():
    from pymorphy3 import MorphAnalyzer
    return MorphAnalyzer()


def tokens(text: str, morph: bool):
    return [(norm(t.text, morph), t.start, t.stop)
            for t in tokenize(text) if WORD.search(t.text)]


def excluded(text, start, end, phrases, radius=40):
    """An exclusion belongs to an occurrence, not the entire source document."""
    context = text[max(0, start-radius):min(len(text), end+radius)].casefold().replace("ё", "е")
    return any(p.casefold().replace("ё", "е") in context for p in phrases if p)


def _unique_hits(hits):
    # Minimal evidence windows win over their overlapping supersets. Adjacent
    # occurrences remain independent; score is never used as a finding risk.
    selected = []
    for hit in sorted(set(hits), key=lambda h: (h[1]-h[0], -h[2], h[0])):
        if not any(hit[0] < old[1] and old[0] < hit[1] for old in selected):
            selected.append(hit)
            if len(selected) >= 10:
                break
    return sorted(selected)[:10]


def search(text, *, mode="substring", phrases=(), terms=(), window=12,
           ordered=False, min_score=1, exclude_phrases=()):
    """Yield bounded (start, end, score, fraction) hits; return max 10 hits.

    Literal, whole-word and morphology modes treat each phrase as an atomic
    pattern. Flexible mode searches weighted term groups within a word window.
    """
    lower = text.casefold().replace("ё", "е")
    def accepted(start, end):
        return not excluded(text, start, end, exclude_phrases)

    if mode == "substring":
        hits = []
        for phrase in phrases[:30]:
            pattern = phrase.casefold().replace("ё", "е")
            if not pattern:
                continue
            for match in re.finditer(re.escape(pattern), lower):
                if accepted(match.start(), match.end()):
                    hits.append((match.start(), match.end(), 1, 1.0))
        return _unique_hits(hits)
    morph = mode in {"morphology", "flexible"}
    stream = tokens(text, morph)
    if not stream:
        return []
    if mode in {"word", "morphology"}:
        result = []
        for phrase in phrases[:30]:
            pattern = [t[0] for t in tokens(phrase, morph)]
            if not pattern:
                continue
            size = len(pattern)
            for j in range(len(stream) - size + 1):
                if [x[0] for x in stream[j:j+size]] == pattern:
                    start, end = stream[j][1], stream[j+size-1][2]
                    if accepted(start, end):
                        result.append((start, end, 1, 1.0))
        return _unique_hits(result)
    if mode != "flexible":
        return []
    distinct_groups = {}
    for entry in terms[:30]:
        phrase = entry.get("text", "")
        parts = [t[0] for t in tokens(phrase, True)]
        if parts:
            key = tuple(parts)
            weight, required = int(entry.get("weight", 1)), bool(entry.get("required", False))
            if key in distinct_groups:
                old_weight, old_required = distinct_groups[key]
                weight, required = max(weight, old_weight), required or old_required
            distinct_groups[key] = (weight, required)
    groups = [(list(parts), weight, required) for parts, (weight, required) in distinct_groups.items()]
    if not groups:
        return []
    weight_total = sum(w for _,w,_ in groups)
    # Index each term once. A term contributes its weight at most once per
    # window, even if it occurs repeatedly in that window.
    occurrences = []
    words = [item[0] for item in stream]
    for parts, weight, required in groups:
        occurrences.append([i for i in range(len(stream)-len(parts)+1)
                            if words[i:i+len(parts)] == parts])
    anchors = sorted({i for positions in occurrences for i in positions})
    hits = []
    for start in anchors:
        end = min(len(stream), start + max(1, min(80, int(window))))
        found = []
        for (parts, weight, required), positions in zip(groups, occurrences):
            index = bisect_left(positions, start)
            if ordered and found:
                index = bisect_left(positions, found[-1][1]+1)
            if index < len(positions):
                i = positions[index]
                if i + len(parts) <= end:
                    found.append((i,i+len(parts)-1,weight,required))
        if len(found) != len(groups) and any(g[2] for g in groups) and sum(1 for f in found if f[3]) < sum(1 for g in groups if g[2]):
            continue
        if ordered and found != sorted(found, key=lambda x: x[0]):
            continue
        score = sum(f[2] for f in found)
        if score < min_score or not found:
            continue
        first = min(f[0] for f in found)
        last = max(f[1] for f in found)
        left, right = stream[first][1], stream[last][2]
        if accepted(left, right):
            hits.append((left, right, score, round(score/max(1,weight_total),3)))
    return _unique_hits(hits)
