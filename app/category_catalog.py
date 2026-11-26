"""Shared category identity and detection-method metadata, without ORM imports."""
import re
import unicodedata

from app.detector_catalog import DETECTORS

LEGACY_ALIASES = {"RU_INN": "INN", "RU_PHONE": "PHONE"}
# These detectors yield native text evidence before the custom matcher.
# File-only and reference detectors are not evaluated a second time.
CONTEXT_CATEGORIES = frozenset({
    "EMAIL", "PHONE", "INN", "RU_SNILS", "RU_PASSPORT", "SECRET", "PRIVATE_KEY",
    "CONFIDENTIAL", "PROMPT_INJECTION", "CODE", "SUSPICIOUS_COMMAND",
})
CONTEXT_KINDS = frozenset({"keywords", "regex"})
CONTEXT_MARKER = "builtin_context"

def detector_name(category_id):
    key = LEGACY_ALIASES.get(category_id, category_id)
    return next((label for label, _, ids in DETECTORS.values() if key in ids), "")

def normalized_name(name):
    value = unicodedata.normalize("NFKC", name).casefold().replace("ё", "е")
    value = re.sub(r"^\s*\[ru\d+\]\s*", "", value)
    return " ".join(re.findall(r"\w+", value))

# Deliberately conservative lexical hints, not a semantic classifier.
_IDENTIFIER_HINTS = {
    "RU_SNILS": r"\b(?:снилс|snils)\b",
    "INN": r"\b(?:инн|inn)\b",
    "RU_PASSPORT": r"\b(?:паспорт\w*|passport)\b",
    "PHONE": r"\b(?:телефон\w*|phone)\b",
    "EMAIL": r"\b(?:email|e mail|электронн\w* почт\w*)\b",
}

def possible_duplicates(name, rows, exclude_id=None):
    normalized = normalized_name(name)
    result = []
    for key, existing in rows:
        if key == exclude_id or key in LEGACY_ALIASES:
            continue
        hint = _IDENTIFIER_HINTS.get(key)
        if normalized and (normalized == normalized_name(existing) or
                           (hint and re.search(hint, normalized))):
            result.append((key, existing))
    return result
