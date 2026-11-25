"""Explicit test-install cleanup through Django ORM, with preservation hashes.

Requires stopped producers/workers. No database backup is created.
Refuses any message not identified by benchmark corpus bytes or smoke import.
"""
import hashlib
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mice.settings')


def main():
    import django
    django.setup()
    from django.apps import apps
    from django.db import transaction
    from records import models as r
    from pipeline.models import WorkItem
    from policy_engine.models import Evaluation, AnalysisRevision
    hashes = {hashlib.sha256(p.read_bytes()).hexdigest() for p in
              (ROOT / 'test-data/benchmark-350-v1/eml').glob('*.eml')}
    identified = set(r.Message.objects.filter(original_sha_ref_id__in=hashes).values_list('pk', flat=True))
    identified.update(r.ImportRecord.objects.filter(name='smoke.eml', message__subject__startswith='MICE final smoke ').values_list('message_id', flat=True))
    if r.Message.objects.exclude(pk__in=identified).exists():
        raise RuntimeError('Unidentified non-test mail: abort cleanup')
    if r.Message.objects.filter(legal_hold=True).exists():
        raise RuntimeError('Legal hold: abort cleanup')
    allowed = {'ingestion.parse','extraction.extract','ocr.complete','detection.detect','policy.evaluate',
               'notifications.deliver','maintenance.resources','maintenance.recover','maintenance.retention'}
    if WorkItem.objects.exclude(kind__in=allowed).exists() or r.Job.objects.exists():
        raise RuntimeError('Unreviewed work exists: abort cleanup')
    def protected():
        labels = ['records.Category','records.CategoryRule','records.Policy','records.Setting',
                  'records.Reference','records.MLModel','records.MLDataset','records.TrainingExample',
                  'records.Account','records.Identity','records.Address','records.LoginSession',
                  'identity.User','auth.Group','auth.Permission','pipeline.PeriodicSchedule',
                  'policy_engine.PolicyRevision','records.InferenceArtifact']
        result = {}
        for label in labels:
            model = apps.get_model(label)
            manager = getattr(model, 'all_objects', model._base_manager)
            values = list(manager.order_by(model._meta.pk.name).values())
            # Incident provenance is nullable by design; training data survives.
            if label == 'records.TrainingExample':
                for row in values:
                    row.pop('source_incident_id', None)
            result[label] = {'count': len(values), 'sha256': hashlib.sha256(
                json.dumps(values, sort_keys=True, default=str).encode()).hexdigest()}
        return result
    before = protected()
    deleted = {}
    with transaction.atomic():
        targets = set(identified)
        targets.update(map(str, WorkItem.objects.values_list('pk', flat=True)))
        targets.update(r.Incident.objects.values_list('pk', flat=True))
        targets.update(r.Attachment.objects.values_list('pk', flat=True))
        targets.update(r.MailEvent.objects.values_list('pk', flat=True))
        def remove(name, query):
            deleted[name] = query.delete()[0]
        remove('evaluations', Evaluation.objects.all())
        remove('analysis_revisions', AnalysisRevision.objects.all())
        remove('work_items_and_dispatch_attempts', WorkItem.objects.all())
        remove('comments', r.Comment.objects.all())
        remove('notification_outbox', r.Outbox.objects.all())
        remove('incidents', r.Incident.objects.all())
        remove('imports', r.ImportRecord.objects.all())
        remove('events', r.MailEvent.objects.all())
        remove('attachments', r.Attachment.objects.all())
        remove('messages', r.Message.objects.all())
        remove('contents', r.Content.objects.all())
        remove('test_audit', r.Audit.objects.filter(target__in=targets))
        remove('metrics', r.Metric.objects.all())
        remove('diagnostics', r.Diagnostic.objects.all())
        remove('ocr_test_documents', r.OCRTestDocument.objects.all())
        remove('mail_semantic_chunks', r.SemanticChunk.objects.filter(source_type__in=['message','attachment'], source_id__in=targets))
        referenced = set(r.Reference.objects.values_list('blob_sha_ref_id', flat=True))
        remove('unused_blobs', r.Blob.objects.exclude(pk__in=referenced))
        after = protected()
        if before != after:
            raise RuntimeError('Protected configuration changed: rolling back')
    output = {'deleted': deleted, 'preserved_before': before, 'preserved_after': after,
              'no_database_backup_created': True, 'remaining_messages': r.Message.objects.count(),
              'remaining_jobs': WorkItem.objects.count()}
    path = ROOT / 'test-data/results-benchmark350-clean-reimport'
    path.mkdir(exist_ok=True)
    (path / 'cleanup.json').write_text(json.dumps(output, indent=2))
    print(json.dumps(deleted, indent=2))


if __name__ == '__main__':
    main()