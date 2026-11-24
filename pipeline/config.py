"""Per-group process/resource settings. No heavy application imports."""

import os

GROUPS = (
    "ingestion",
    "extraction",
    "ocr",
    "detection",
    "ml",
    "llm",
    "policy",
    "notifications",
    "training",
    "maintenance",
)


def limits(group):
    if group not in GROUPS:
        raise ValueError(f"Unknown worker group: {group}")
    prefix = "MICE_" + group.upper() + "_"
    hard = int(os.environ.get(prefix + "TIMEOUT", "7200" if group == "training" else "300"))
    soft = int(os.environ.get(prefix + "SOFT_TIMEOUT", str(max(1, hard - 15))))
    concurrency = int(os.environ.get(prefix + "CONCURRENCY", "1"))
    prefetch = int(os.environ.get(prefix + "PREFETCH", "1"))
    if min(hard, soft, concurrency, prefetch) < 1 or soft >= hard:
        raise ValueError(f"Invalid worker limits for {group}")
    return {
        "hard": hard,
        "soft": soft,
        "concurrency": concurrency,
        "prefetch": prefetch,
        "max_memory_kb": int(os.environ.get(prefix + "MAX_MEMORY_KB", "0")),
        "max_tasks": int(os.environ.get(prefix + "MAX_TASKS", "0")),
    }
