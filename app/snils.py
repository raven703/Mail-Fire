"""Shared SNILS normalization, checksum and contextual candidate recognition."""

import re

_CANDIDATE = re.compile(r"(?<!\w)[0-9]{3}[\s\-–—]*[0-9]{3}[\s\-–—]*[0-9]{3}[\s\-–—]*[0-9]{2}(?!\w)")
_CONTEXT = re.compile(r"\bснилс\b|страхов(?:ой|ого)\s+номер|индивидуального\s+лицевого\s+сч[её]та", re.I)


def normalize_snils(value):
    if re.search(r"[^0-9\s\-–—]", value):
        return ""
    return re.sub(r"[^0-9]", "", value)


def snils_valid(value):
    digits = normalize_snils(value)
    if len(digits) != 11 or digits[:9] == "000000000":
        return False
    total = sum(int(d) * weight for d, weight in zip(digits[:9], range(9, 0, -1)))
    checksum = total if total < 100 else 0 if total in (100, 101) else total % 101
    if checksum == 100:
        checksum = 0
    return int(digits[-2:]) == checksum


def snils_matches(text):
    matches = []
    for match in _CANDIDATE.finditer(text):
        digits = normalize_snils(match.group())
        if digits[:9] == "000000000":
            continue
        valid = snils_valid(match.group())
        before = re.split(r"\n\s*\n", text[max(0, match.start()-180):match.start()])[-1]
        after = re.split(r"\n\s*\n", text[match.end():match.end()+80])[0]
        if not valid and not _CONTEXT.search(before + " " + after):
            continue
        matches.append({"start": match.start(), "end": match.end(),
                        "checksum_valid": valid, "verification": "confirmed" if valid else "suspected",
                        "confidence": 0.85 if valid else 0.45,
                        "reason": "СНИЛС: контрольная сумма валидна; не проверка по реестру" if valid else
                        "Предполагаемый СНИЛС: явный контекст, но неверная контрольная сумма; требуется проверка"})
    return matches