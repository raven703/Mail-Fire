"""Conservative, audited recovery of parser DEAD jobs; preview by default."""
import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from pipeline.models import WorkItem
from pipeline.services import retry
from records.models import Attachment, Audit, Message


def eligibility(job):
    if job.status != 'DEAD' or job.kind not in {'ingestion.parse', 'extraction.extract', 'detection.detect'}:
        return 'not_parser_dead'
    if job.error != 'HTTPStatusError' and not ('status=503' in job.error or 'status=429' in job.error):
        return 'requires_manual_error_review'
    message_id = job.payload.get('message_id')
    message = Message.objects.select_for_update().filter(pk=message_id).first()
    if not message:
        return 'missing_message'
    # Replaying an old parse/extraction after reanalysis could overwrite current
    # evidence. Newer completed chains must be retained, never replayed over.
    if WorkItem.objects.filter(payload__message_id=message_id, kind=job.kind,
                               created_at__gt=job.created_at).exists():
        return 'superseded_by_newer_stage'
    if WorkItem.objects.filter(payload__message_id=message_id, status__in=['PENDING', 'RUNNING']).exists():
        return 'message_busy'
    if job.kind == 'extraction.extract':
        if Attachment.objects.filter(message=message).exists():
            return 'attachment_evidence_exists'
        parent = WorkItem.objects.filter(pk=job.payload.get('parse_job_id'), kind='ingestion.parse', status='DONE').first()
        if not parent:
            return 'invalid_parent'
    if job.kind == 'detection.detect':
        parent = WorkItem.objects.filter(pk=job.payload.get('ocr_job_id'), kind='ocr.complete', status='DONE').first()
        if not parent:
            return 'invalid_parent'
    return 'eligible'


class Command(BaseCommand):
    help = 'Preview safe recovery; --apply requires an immutable reviewed --plan file.'

    def add_arguments(self, parser):
        parser.add_argument('--plan', required=True)
        parser.add_argument('--apply', action='store_true')

    def handle(self, *args, **options):
        path = Path(options['plan'])
        if not options['apply']:
            if path.exists():
                raise CommandError('Do not overwrite an existing plan')
            rows = []
            for identifier in WorkItem.objects.filter(status='DEAD').values_list('pk', flat=True):
                with transaction.atomic():
                    job = WorkItem.objects.select_for_update().get(pk=identifier)
                    rows.append({'id': str(job.pk), 'kind': job.kind, 'error': job.error,
                                 'message_id': job.payload.get('message_id'), 'decision': eligibility(job)})
            path.write_text(json.dumps(rows, indent=2))
        else:
            rows = json.loads(path.read_text())
            for row in rows:
                if row['decision'] != 'eligible':
                    continue
                with transaction.atomic():
                    job = WorkItem.objects.select_for_update().get(pk=row['id'])
                    decision = eligibility(job)
                    if decision == 'eligible':
                        retry(job.pk)
                        Audit.objects.create(actor='system:parser-recovery', action='parser_dead_retry',
                                             target=str(job.pk), details={'previous_error': job.error})
                    row['application_decision'] = decision
            Path(str(path)+'.applied.json').write_text(json.dumps(rows, indent=2))
        from collections import Counter
        self.stdout.write(json.dumps(dict(Counter(r.get('application_decision', r['decision']) for r in rows))))