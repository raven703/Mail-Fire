from app.fingerprints import compare, fingerprint


def test_modified_document_and_fragments():
    original = (
        "Confidential internal business forecast budget strategy revenue and expenses for next financial year"
    )
    result = compare("Forwarded excerpt: " + original + " Added comment", original, fingerprint(original))
    assert result["reference_coverage"] == 1
    assert result["matched_fragments"]
    assert not result["exact"]
    assert compare(original.upper(), original, fingerprint(original))["exact"]


def test_unrelated_document():
    assert (
        compare(
            "Public picnic invitation meeting friends and family",
            "",
            fingerprint("Confidential business financial strategy and forecast"),
        )["reference_coverage"]
        == 0
    )
