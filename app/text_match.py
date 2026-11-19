"""Bounded CPU-only Russian-aware keyword and flexible phrase matcher.

Default literal matching is kept for imported rulepacks. Morphology uses a
Russian word-form stemmer (and pymorphy3 when installed), without requiring a
downloaded model. Each configured term scores at most once per window.
"""
import re
from functools import lru_cache

WORD = re.compile(r"[^\W_]+", re.UNICODE)
# Productive inflections; conservative fallback if pymorphy3 is unavailable.
ENDINGS = tuple(sorted((
    "иями","ями","ами","иями","иями","ов","ев","ей","ие","ые","ое","ее",
    "ого","его","ому","ему","ими","ыми","ая","яя","ую","юю","ий",
    "ый","ой","ам","ям","ах","ях","ом","ем","у","ю","а","я",
    "ы","и","е","о","ь","й","ов","ев","ть","ти","ться","тся",
    "ешь","ете","ем","ет","ут","ют","ат","ят","ил","ила","или",
    "али","ала","айте","ите","ейте","ия","иям","иях",
), key=len, reverse=True))

@lru_cache(maxsize=8192)
def norm(word: str, morph: bool = False) -> str:
    word = word.casefold().replace("ё", "е")
    if not morph or not re.search(r"[а-я]", word):
        return word
    try:
        from pymorphy3 import MorphAnalyzer
    except ImportError:
        # Conservative suffix approximation for constrained installations.
        for ending in ENDINGS:
            if len(word) > len(ending) + 3 and word.endswith(ending):
                return word[:-len(ending)]
        return word
    return _morph().parse(word)[0].normal_form.replace("ё", "е")


@lru_cache(maxsize=1)
def _morph():
    from pymorphy3 import MorphAnalyzer
    return MorphAnalyzer()


def tokens(text: str, morph: bool):
    return [(norm(m.group(), morph), m.start(), m.end()) for m in WORD.finditer(text)]


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
            pattern = [norm(w.group(), morph) for w in WORD.finditer(phrase)]
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
        parts = [norm(w.group(), True) for w in WORD.finditer(phrase)]
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
