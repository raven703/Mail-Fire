"""Conservative obfuscation recovery for threat-classification context.

Never overwrite source evidence or treat a recovered string as proof of a threat.
"""
import re
import unicodedata

ZERO_WIDTH = re.compile("[\u200b-\u200f\u2060\ufeff]")
TOKEN = re.compile(r"[A-Za-zА-Яа-яЁё0-9]{3,}")
CONFUSABLES = str.maketrans({
    "a": "а", "c": "с", "e": "е", "o": "о", "p": "р",
    "x": "х", "y": "у", "k": "к", "m": "м", "t": "т",
    "A": "А", "C": "С", "E": "Е", "O": "О", "P": "Р",
    "X": "Х", "Y": "У", "K": "К", "M": "М", "T": "Т",
})
DIGITS = str.maketrans({"0": "о", "3": "з", "4": "ч", "6": "б"})
SEPARATED = re.compile(r"(?<!\w)(?:[А-Яа-яЁё]\s*[.·_\-]\s*){2,}[А-Яа-яЁё](?!\w)")

DEFAULTS = {"enabled": False, "mode": "detect", "sensitivity": "medium"}


def normalize(text: str, sensitivity: str = "medium") -> tuple[str, list[str]]:
    """Return a *separate* variant and transformation markers."""
    if sensitivity not in {"low", "medium", "high"}:
        raise ValueError("Unknown sensitivity")
    changes = []
    recovered = unicodedata.normalize("NFKC", text)
    if recovered != text:
        changes.append("unicode_nfkc")
    cleaned = ZERO_WIDTH.sub("", recovered)
    if cleaned != recovered:
        changes.append("invisible_characters")
    recovered = cleaned
    if sensitivity in {"medium", "high"}:
        def restore(match):
            word = match.group()
            has_cyrillic = bool(re.search("[А-Яа-яЁё]", word))
            if not has_cyrillic:
                return word
            candidate = word.translate(CONFUSABLES).translate(DIGITS)
            return candidate
        cleaned = TOKEN.sub(restore, recovered)
        if cleaned != recovered:
            changes.append("mixed_script_or_digits")
        recovered = cleaned
    if sensitivity == "high":
        cleaned = SEPARATED.sub(lambda m: re.sub(r"[.·_\-\s]", "", m.group()), recovered)
        if cleaned != recovered:
            changes.append("separated_letters")
        recovered = cleaned
    return recovered, changes
