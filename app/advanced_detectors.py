"""Offline recognizers and bounded static analysis. Never executes submitted code."""

from functools import lru_cache

from app.detectors import inn_valid


def snils_valid(value):
    digits = "".join(c for c in value if c.isdigit())
    if len(digits) != 11:
        return False
    checksum = sum(int(d) * w for d, w in zip(digits[:9], range(9, 0, -1))) % 101
    return int(digits[-2:]) == (0 if checksum == 100 else checksum)


@lru_cache
def recognizers():
    from presidio_analyzer import Pattern, PatternRecognizer

    class RussianRecognizer(PatternRecognizer):
        def validate_result(self, pattern_text):
            if self.supported_entities == ["RU_INN"]:
                return inn_valid(pattern_text)
            if self.supported_entities == ["RU_SNILS"]:
                return snils_valid(pattern_text)
            return None

    return [
        RussianRecognizer(
            supported_entity=entity, supported_language="ru", patterns=[Pattern(entity, pattern, score)]
        )
        for entity, pattern, score in [
            ("RU_INN", r"(?<!\d)(?:\d{12}|\d{10})(?!\d)", 0.85),
            ("RU_SNILS", r"(?<!\d)\d{3}[- ]?\d{3}[- ]?\d{3} ?\d{2}(?!\d)", 0.85),
            ("RU_PASSPORT", r"(?i)паспорт\s*[:№]?\s*\d{2}\s?\d{2}\s?\d{6}(?!\d)", 0.8),
            ("RU_PHONE", r"(?<!\d)(?:\+7|8)[ ()-]*\d{3}[ ()-]*\d{3}[ -]*\d{2}[ -]*\d{2}(?!\d)", 0.7),
        ]
    ]


def finding(category, source, excerpt="", risk=80, reason="Требуется проверка аналитиком", **extra):
    return dict(
        category=category,
        source=source,
        rule_id=category.lower(),
        risk=risk,
        excerpt=excerpt[:500],
        reason=reason,
        confidence=None,
        start=0,
        end=0,
        version="advanced-1",
        status="ANALYZED",
        **extra,
    )


def pii(text):
    output = []
    for recognizer in recognizers():
        for match in recognizer.analyze(text, recognizer.supported_entities):
            if match.score:
                result = finding(
                    match.entity_type,
                    "presidio",
                    text[match.start : match.end],
                    60,
                    "Российский распознаватель Presidio; ИНН/СНИЛС проверены контрольной суммой",
                )
                result.update(confidence=match.score, start=match.start, end=match.end)
                output.append(result)
    return output


@lru_cache
def yara_rules():
    import yara

    return yara.compile(
        source=r"""
rule Suspicious_Encoded_PowerShell {
 strings: $a = "powershell" nocase $b = "-encodedcommand" nocase $c = "-enc " nocase
 condition: $a and ($b or $c)
}
rule Executable_PE { strings: $mz = {4D 5A} condition: $mz at 0 and uint32(uint32(0x3c)) == 0x00004550 }
rule EICAR_Test_File { strings: $a = "EICAR-STANDARD-ANTIVIRUS-TEST-FILE" condition: $a }
"""
    )


def static_scan(data, name):
    from app.secret_scan import scan

    secrets = scan(data)
    results = [
        finding("YARA", "yara", risk=85, reason="Статическое правило: " + match.rule, filename=name)
        for match in yara_rules().match(data=data, timeout=10)
    ]
    if name.lower().endswith((".doc", ".docm", ".xls", ".xlsm", ".ppt", ".pptm", ".rtf")):
        from oletools.olevba import VBA_Parser

        parser = VBA_Parser(name or "attachment", data=data)
        try:
            if parser.detect_vba_macros():
                for kind, keyword, description in parser.analyze_macros() or []:
                    if kind in {"AutoExec", "Suspicious", "IOC"}:
                        results.append(
                            finding("OFFICE_MACRO", "oletools", keyword, 80, description, filename=name)
                        )
        finally:
            parser.close()
    return {
        "findings": results + secrets["findings"],
        "engines": {"yara": "OK", "oletools": "OK", "gitleaks": secrets["status"]},
    }
