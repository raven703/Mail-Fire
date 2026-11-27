"""Optional grouped or preassigned splits for native supervised trainers."""

import numpy as np


SPLITS = ("train", "validation", "test")


def partition(groups):
    """Return text-hash partitions, or None for the legacy trainer split.

    ``groups`` maps normalized text hashes to examples. All examples must use
    the same metadata mode: ``split`` for an external split, or ``group_id``
    for a deterministic 60/20/20 group split. The caller validates labels.
    """
    rows = list(groups.items())
    has_split = ["split" in item for _, item in rows]
    has_group = ["group_id" in item for _, item in rows]
    if not any(has_split) and not any(has_group):
        return None
    if any(has_split) and not all(has_split):
        raise ValueError("Every example needs split metadata")
    if not all(has_split) and not all(has_group):
        raise ValueError("Every example needs split or group_id metadata")
    group_ids = {}
    for key, item in rows:
        group = item.get("group_id", key)
        if not isinstance(group, str) or not group.strip():
            raise ValueError("group_id must be a nonempty string")
        group_ids[key] = group
    if all(has_split):
        result = {name: [] for name in SPLITS}
        assigned = {}
        for key, item in rows:
            split = item["split"]
            if split not in result:
                raise ValueError("split must be train, validation or test")
            group = group_ids[key]
            if group in assigned and assigned[group] != split:
                raise ValueError("Semantic group crosses splits")
            assigned[group] = split
            result[split].append(key)
    else:
        group_names = sorted(set(group_ids.values()))
        np.random.default_rng(42).shuffle(group_names)
        n = len(group_names)
        assigned = {group: ("train" if i < int(n * .6) else "validation" if i < int(n * .8) else "test")
                    for i, group in enumerate(group_names)}
        result = {name: [key for key in sorted(groups) if assigned[group_ids[key]] == name] for name in SPLITS}
    if any(not result[name] for name in SPLITS):
        raise ValueError("Every split needs examples")
    return result
