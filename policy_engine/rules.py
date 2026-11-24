"""Unchanged pure policy/direction functions extracted from source master."""


def policy_matches(findings, conditions):
    """Findings are counted individually; any/all applies to category coverage.

    min_risk is a per-finding threshold, min_count is a total finding count,
    and 'all' additionally needs one qualifying finding from every category.
    Existing policies default to 'any' for backward compatibility.
    """
    requested = set(conditions.get("categories") or [])
    result = [
        f
        for f in findings
        if f["risk"] >= conditions.get("min_risk", 0) and (not requested or f["category"] in requested)
    ]
    if len(result) < conditions.get("min_count", 1):
        return []
    if conditions.get("category_match", "any") == "all":
        if not requested or not requested.issubset({f["category"] for f in result}):
            return []
    return result


def classify_direction(sender, recipients, internal_domains):
    """Conservative direction inference based only on message addresses.

    SMTP BCC collector recipient is not necessarily an original recipient.
    """
    domains = {d.strip().lower().lstrip("@") for d in internal_domains.split(",") if d.strip()}
    if not domains:
        return "UNKNOWN"

    def is_internal(address):
        address = (address or "").strip().lower()
        if address.count("@") != 1:
            return None
        domain = address.rsplit("@", 1)[1]
        return domain in domains or any(domain.endswith("." + d) for d in domains)

    src = is_internal(sender)
    dst = {is_internal(addr) for addr in recipients if addr}
    if src is None or not dst or None in dst:
        return "UNKNOWN"
    if src and False in dst:
        return "OUTBOUND"
    if not src and True in dst:
        return "INBOUND"
    if src and dst == {True}:
        return "INTERNAL"
    return "UNKNOWN"
