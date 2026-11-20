"""Conservative Russian passport fields; never treat a bare number as identity data."""

import re

_SEP = r"[\s,;:№#|/\\.\-–—]*"
_SERIES = r"\d{2}[\s\-–—]*\d{2}"
_NUMBER = r"\d{6}"
_FIELDS = re.compile(
    rf"(?<!\w)(?:серия{_SEP})?{_SERIES}{_SEP}"
    rf"(?:(?:номер|ном\.?|№){_SEP})?{_NUMBER}(?!\w)", re.I
)
_TABLE = re.compile(
    rf"\bсерия{_SEP}(?:номер|№){_SEP}{_SERIES}{_SEP}{_NUMBER}(?!\w)", re.I
)
_CONTEXT = re.compile(r"\bпаспорт(?:а|ом|е|у)?\b(?!\s+(?:проекта|изделия|оборудования)\b)", re.I)


def passport_spans(text):
    """Require a passport mention within the same local field block (160 chars).

    Blank paragraphs delimit unrelated text. Whitespace/newlines within tables
    are accepted; passport labels without series AND number are insufficient.
    """
    result = []
    for pattern in (_FIELDS, _TABLE):
        for match in pattern.finditer(text):
            start, end = match.span()
            digits = re.sub(r"\D", "", match.group())
            if len(digits) != 10 or digits[:4] == "0000" or digits[4:] == "000000":
                continue
            prefix = text[max(0, start - 160):start]
            suffix = text[end:end + 80]
            local = re.split(r"\n\s*\n", prefix)[-1] + match.group() + re.split(r"\n\s*\n", suffix)[0]
            if _CONTEXT.search(local) and not any(a <= start and end <= b for a, b in result):
                result.append((start, end))
    return result