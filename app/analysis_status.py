"""Message completeness is relative to configured analysis, not optional engines.

Genuine failures and unsupported attachments still produce PARTIAL.
Explicitly skipped optional checks are reported separately for auditability.
"""

def classify_analysis(attachments, antivirus_states, ml_errors, llm_errors, *,
                      antivirus_enabled=True, ml_enabled=True, ocr_enabled=True):
    """Return (message_status, skipped_checks) without masking actual errors.

    attachments: (status, extraction_details) pairs.
    """
    partial = False
    skipped = set()
    for status, details in attachments:
        details = details or {}
        if status == "ANALYZED":
            continue
        if (status == "PARTIAL" and not ocr_enabled
                and details.get("ocr_required") is True
                and not details.get("error")):
            skipped.add("ocr")
            continue
        partial = True
    if antivirus_enabled:
        for state in antivirus_states:
            if state == "DISABLED":
                skipped.add("antivirus")
            elif state not in {"OK", "FOUND"}:
                partial = True
    elif antivirus_states:
        skipped.add("antivirus")
    if ml_enabled:
        if ml_errors:
            partial = True
    else:
        skipped.add("ml")
    # Disabled LLM never returns an error; enabled but failing LLM is incomplete.
    if llm_errors:
        partial = True
    return ("PARTIAL" if partial else "ANALYZED"), sorted(skipped)
