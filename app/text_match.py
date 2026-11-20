"""Bounded CPU-only Russian-aware keyword and flexible phrase matcher.

Default literal matching is kept for imported rulepacks. Morphology uses
Razdel tokenization and pymorphy3 dictionaries, without downloaded model
weights. Each configured term scores at most once per window.
"""
import re
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


def search(text, *, mode="substring", phrases=(), terms=(), window=12,
           ordered=False, min_score=1, exclude_phrases=()):
    """Yield bounded (start, end, score, fraction) hits; return max 10 hits.

    Literal, whole-word and morphology modes treat each phrase as an atomic
    pattern. Flexible mode searches weighted term groups within a word window.
    """
    lower = text.casefold().replace("ё", "е")
    if any(p.casefold().replace("ё", "е") in lower for p in exclude_phrases):
        return []
    if mode == "substring":
        hits = []
        for phrase in phrases[:30]:
            pos = lower.find(phrase.casefold().replace("ё", "е"))
            if pos >= 0:
                hits.append((pos, pos + len(phrase), 1, 1.0))
        return hits[:10]
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
                    result.append((stream[j][1], stream[j+size-1][2], 1, 1.0))
                    break
        return result[:10]
    if mode != "flexible":
        return []
    groups = []
    for entry in terms[:30]:
        phrase = entry.get("text", "")
        parts = [t[0] for t in tokens(phrase, True)]
        if parts:
            groups.append((parts, int(entry.get("weight", 1)), bool(entry.get("required", False))))
    if not groups:
        return []
    weight_total = sum(w for _,w,_ in groups)
    seen = set()
    hits = []
    for start in range(len(stream)):
        end = min(len(stream), start + max(1, min(80, int(window))))
        found = []
        for parts, weight, required in groups:
            for i in range(start, end-len(parts)+1):
                if [t[0] for t in stream[i:i+len(parts)]] == parts:
                    found.append((i,i+len(parts)-1,weight,required))
                    break
        if len(found) != len(groups) and any(g[2] for g in groups) and sum(1 for f in found if f[3]) < sum(1 for g in groups if g[2]):
            continue
        if ordered and found != sorted(found, key=lambda x: x[0]):
            continue
        score = sum(f[2] for f in found)
        if score < min_score or not found:
            continue
        first = min(f[0] for f in found)
        last = max(f[1] for f in found)
        key = (first,last)
        if key in seen:
            continue
        seen.add(key)
        hits.append((stream[first][1],stream[last][2],score,round(score/max(1,weight_total),3)))
        if len(hits) >= 10:
            break
    return hits
