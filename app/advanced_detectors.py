"""Offline recognizers and bounded static analysis. Never executes submitted code."""

from functools import lru_cache

from app.detectors import inn_valid
from app.snils import snils_matches, snils_valid


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


def pii(text, *, disabled=()):
    output = []
    for match in snils_matches(text):
        if "RU_SNILS" in disabled:
            break
        output.append(finding(
            "RU_SNILS", "presidio", text[match["start"]:match["end"]],
            60 if match["checksum_valid"] else 40, match["reason"],
        ) | match)
    from app.passport import passport_spans

    for start, end in passport_spans(text):
        if "RU_PASSPORT" in disabled:
            break
        output.append(finding(
            "RU_PASSPORT", "presidio", text[start:end], 60,
            "Серия и номер паспорта в контексте паспортных реквизитов",
        ) | {"start": start, "end": end, "confidence": 0.8})
    # INN (same checksum algorithm) and PHONE are emitted once by detect().
    return output


YARA_SOURCE = r"""
rule Suspicious_Encoded_PowerShell {
 strings: $a = "powershell" nocase $b = "-encodedcommand" nocase $c = "-enc " nocase
 condition: $a and ($b or $c)
}
rule Executable_PE { strings: $mz = {4D 5A} condition: $mz at 0 and uint32(uint32(0x3c)) == 0x00004550 }
rule EICAR_Test_File { strings: $a = "EICAR-STANDARD-ANTIVIRUS-TEST-FILE" condition: $a }
"""


@lru_cache
def yara_rules():
    import yara

    return yara.compile(source=YARA_SOURCE)


def static_scan(data, name, *, engines=None):
    from app.secret_scan import scan

    engines = engines or {"static_files": True, "secrets": True}
    secrets = scan(data) if engines.get("secrets", True) else {"findings": [], "status": "DISABLED"}
    results = [
        finding("YARA", "yara", risk=85, reason="Статическое правило: " + match.rule, filename=name)
        for match in (yara_rules().match(data=data, timeout=10) if engines.get("static_files", True) else [])
    ]
    if engines.get("static_files", True) and name.lower().endswith((".doc", ".docm", ".xls", ".xlsm", ".ppt", ".pptm", ".rtf")):
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
        "engines": {"yara": "OK" if engines.get("static_files", True) else "DISABLED",
                    "oletools": "OK" if engines.get("static_files", True) else "DISABLED", "gitleaks": secrets["status"]},
    }
