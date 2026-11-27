"""Resolve presentation only from saved analysis snapshots, never live config."""
import json

from django import template

from policy_engine.models import AnalysisRevision
from records.models import Attachment, CategoryRule, Content, Message, Setting

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
        for key in ("category", "rule_id", "source", "rule_version"):
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
        if message is not None and not row.get("historical_rule"):
            archive = Setting.objects.filter(pk="dlp_ru2_history").first()
            if archive:
                rule = archive.value.get("rules", {}).get(row.get("rule_id"))
                if rule:
                    row["historical_rule"] = rule
                    row["historical_category"] = archive.value.get("categories", {}).get(row.get("category"), row.get("category"))
        result.append(row)
    return result

def group_findings(findings, document_names=None):
    """Group only for display. Preserve every finding and historical rule revision."""
    document_names = document_names or {}
    groups = {}
    for finding in findings:
        row = dict(finding)
        rule = row.get("historical_rule") or {}
        # Do not present parameters from two revisions as one historical rule.
        key = (row.get("category"), row.get("rule_id"), row.get("source"),
               row.get("historical_category"), row.get("rule_version"), row.get("version"),
               json.dumps(rule, sort_keys=True, ensure_ascii=False))
        if key not in groups:
            groups[key] = {"finding": row, "risk": row.get("risk") or 0, "matches": []}
        group = groups[key]
        group["risk"] = max(group["risk"], row.get("risk") or 0)
        document_id = row.get("document_id")
        if document_id == "body":
            row["document_label"] = "Тело письма"
        elif document_id in document_names:
            row["document_label"] = "Вложение: " + document_names[document_id]
        elif row.get("filename"):
            row["document_label"] = "Файл: " + row["filename"]
        elif not document_id or document_id == "message":
            row["document_label"] = "Письмо (источник не уточнён)"
        else:
            row["document_label"] = "Документ: " + str(document_id)
        group["matches"].append(row)
    return list(groups.values())


def group_categories(groups):
    """Optional category-level presentation; retain all original method groups."""
    result = {}
    for group in groups:
        cid = group['finding'].get('category')
        bucket = result.setdefault(cid, {'category':cid, 'name':group['finding'].get('historical_category') or cid,
                                        'methods':[], 'groups':[]})
        for row in [group['finding']] + group['finding'].get('supporting_rules', []):
            method = row.get('ml_engine') or row.get('source', '')
            if method not in bucket['methods']:
                bucket['methods'].append(method)
        bucket['groups'].append(group)
    return list(result.values())


@register.simple_tag(takes_context=True)
def category_findings(context, findings):
    return group_categories(grouped_findings(context, findings))


@register.simple_tag(takes_context=True)
def grouped_findings(context, findings):
    incident = context.get("incident")
    if not findings and incident is not None:
        # Older incidents may have only policy-hit evidence. Collapse exact
        # duplicates across policies, without changing the stored findings.
        findings = []
        seen = set()
        for hit in getattr(incident, "policy_hits", []) or []:
            for row in hit.get("findings", []):
                key = json.dumps(row, sort_keys=True, ensure_ascii=False)
                if key not in seen:
                    seen.add(key)
                    findings.append(row)
    rows = historical_findings(context, findings)
    message = getattr(incident, "message", None) if incident is not None else context.get("message")
    attachment = context.get("attachment")
    if message is None and isinstance(attachment, Attachment):
        message = attachment.message
    names = {}
    if isinstance(message, Message):
        document_ids = {row.get("document_id") for row in rows} - {None, "", "body", "message"}
        if document_ids:
            names.update(Attachment.objects.filter(message=message, pk__in=document_ids).values_list("pk", "name"))
            missing = document_ids - names.keys()
            if missing:
                # PR #18 preserves old attachment identities in previous Content.
                ids = [value for value in AnalysisRevision.objects.filter(message=message).values_list(
                    "results__content_id", flat=True
                ) if isinstance(value, str)]
                for snapshot in Content.objects.filter(pk__in=ids).values_list("analysis__attachment_snapshot", flat=True):
                    for item in snapshot or []:
                        if isinstance(item, dict) and item.get("id") in missing and isinstance(item.get("name"), str):
                            names[item["id"]] = item["name"]
    return group_findings(rows, names)
