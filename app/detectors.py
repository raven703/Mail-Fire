import re

VERSION = "rules-ru3-1"

TEXT_RULES = (
    ("EMAIL", r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b", 20),
    ("PHONE", r"(?<!\d)(?:\+7|8)[ ()-]*\d{3}[ ()-]*\d{3}[ -]*\d{2}[ -]*\d{2}(?!\d)", 60),
    ("INN", r"(?<!\d)(?:\d{12}|\d{10})(?!\d)", 60),
    (
        "SECRET",
        r'(?i)(?:password|passwd|api[_-]?key|access[_-]?token)\s*[:=]\s*["\x27]?[^\s"\x27]{8,}',
        85,
    ),
    ("PRIVATE_KEY", r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----", 95),
    ("CONFIDENTIAL", r"(?i)коммерческая\s+тайна|строго\s+конфиденциально|trade\s+secret", 65),
    (
        "PROMPT_INJECTION",
        r"(?i)ignore\s+(?:all\s+)?previous\s+instructions|игнорируй\s+(?:все\s+)?предыдущие\s+инструкции|отключи\s+(?:dlp|анализ)",
        60,
    ),
    ("CODE", r"(?m)^\s*(?:def \w+\(|import \w+|function \w+\(|SELECT .+ FROM |#!/bin/(?:ba)?sh)", 15),
    ("SUSPICIOUS_COMMAND", r"(?i)powershell\s+.*-(?:enc|encodedcommand)|curl\s+[^\n]+\|\s*(?:ba)?sh", 80),
)


def inn_valid(value):
    if not value.isascii() or not value.isdigit() or len(set(value)) == 1:
        return False
    digits = list(map(int, value))

    def check(weights):
        return sum(a * b for a, b in zip(digits, weights)) % 11 % 10

    if len(value) == 10:
        return check([2, 4, 10, 3, 5, 9, 4, 6, 8]) == digits[9]
    return (
        len(value) == 12
        and check([7, 2, 4, 10, 3, 5, 9, 4, 6, 8]) == digits[10]
        and check([3, 7, 2, 4, 10, 3, 5, 9, 4, 6, 8]) == digits[11]
    )


def detect(text, *, disabled=()):
    findings = []
    for category, pattern, risk in TEXT_RULES:
        if category in disabled:
            continue
        for match in re.finditer(pattern, text):
            if category == "INN" and not inn_valid(match.group()):
                continue
            hit_risk = risk
            reason = "Совпадение статического правила; требуется проверка контекста"
            if category == "CODE":
                context = text[max(0, match.start()-400):match.end()+400]
                confidential = re.search(r"(?i)конфиденциал\w*|коммерческ\w*\s+тайн\w*|proprietary|internal\s+only|trade\s+secret", context)
                transfer = re.search(r"(?i)переда\w*|высыла\w*|отправ\w*|исходн\w*\s+код|source\s+code|репозитор\w*", context)
                if confidential and transfer:
                    hit_risk = 65
                    reason = "Исходный код с локальными признаками конфиденциальности и передачи"
            findings.append(
                dict(
                    category=category,
                    rule_id=category.lower(),
                    risk=hit_risk,
                    confidence=None,
                    start=match.start(),
                    end=match.end(),
                    excerpt=match.group()[:160],
                    source="text",
                    version=VERSION,
                    reason=reason,
                    status="ANALYZED",
                )
            )
    return findings
