"""Bounded display series from persisted, explicitly scoped service samples."""
from collections import defaultdict


def resource_history(samples):
    groups = defaultdict(list)
    for sample in samples:
        values = sample.values
        total = values.get("ram_total") or 0
        groups[sample.service].append({
            "created_at": sample.created_at,
            "cpu": values.get("cpu_percent"),
            "ram_percent": round(values.get("ram_used", 0) / total * 100, 1) if total else None,
            "ram_used": values.get("ram_used"), "ram_total": total,
            "disk_free": values.get("disk_free"), "swap_used": values.get("swap_used"),
            "scope": values.get("scope", "unknown"),
        })
    return [{"service": service, "latest": rows[0], "rows": rows[:20],
             "series": list(reversed(rows[:20]))} for service, rows in sorted(groups.items())]