"""Deterministic document fingerprints, shingles and explainable fragment overlap."""

import hashlib
import re


def normalize(text):
    return " ".join(re.findall(r"\w+", text.lower(), re.UNICODE))


def fingerprint(text):
    normalized = normalize(text)
    words = normalized.split()
    shingles = {" ".join(words[i : i + 5]) for i in range(max(0, len(words) - 4))}
    signature = [
        min(
            (
                int.from_bytes(hashlib.blake2b((str(seed) + s).encode(), digest_size=8).digest(), "big")
                for s in shingles
            ),
            default=0,
        )
        for seed in range(64)
    ]
    return {
        "sha256": hashlib.sha256(normalized.encode()).hexdigest(),
        "minhash": signature,
        "shingles": sorted(shingles),
        "version": "shingle5-minhash64-v1",
    }


def compare(text, reference_text, reference_fingerprint):
    candidate = fingerprint(text)
    first, second = set(candidate["shingles"]), set(reference_fingerprint["shingles"])
    common = first & second
    exact = candidate["sha256"] == reference_fingerprint["sha256"]
    return {
        "exact": exact,
        "jaccard": len(common) / len(first | second) if first | second else 0,
        "reference_coverage": len(common) / len(second) if second else 0,
        "matched_fragments": sorted(common, key=len, reverse=True)[:20],
        "reason": "Общие последовательности слов; требуется контекстная проверка",
    }
