"""Resolve presentation only from saved analysis snapshots, never live config."""
from django import template

from policy_engine.models import AnalysisRevision
from records.models import CategoryRule

register = template.Library()


@register.simple_tag(takes_context=True)
def historical_findings(context, findings):
    message = context.get("message")
    incident = context.get("incident")
    if incident is not None:
        message = getattr(incident, "message", message)
    snapshots = []
    if message is not None:
        # Revisions remain available even when the message is reanalysed.
        snapshots = [row.results.get("analysis", {}) for row in
                     AnalysisRevision.objects.filter(message=message).order_by("created_at")]
        if message.content_id:
            snapshots.append(message.content.analysis or {})
    deleted = set()
    if message is not None:
        deleted = set(CategoryRule.all_objects.filter(deleted_at__isnull=False,
                      pk__in=[row.get("rule_id") for row in findings or []]).values_list("pk", flat=True))
    result = []
    for finding in findings or []:
        row = dict(finding)
        for key in ("category", "rule_id", "source"):
            row.setdefault(key, "")
        row["rule_deleted"] = row.get("rule_id") in deleted
        for analysis in snapshots:
            if row.get("historical_rule"):
                break
            if row.get("configuration_sha256") and row["configuration_sha256"] != analysis.get("configuration_sha256"):
                continue
            if finding not in analysis.get("findings", []):
                continue
            for group in analysis.get("configuration_snapshot", {}).get("groups", []):
                for rule in group.get("rules", []):
                    if rule["id"] == row.get("rule_id"):
                        row["historical_rule"] = rule
                        row["historical_category"] = group["category"].get("name", group["category"]["id"])
            if row.get("historical_rule"):
                break
        result.append(row)
    return result