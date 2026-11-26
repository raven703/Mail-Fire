from datetime import timedelta
from django.test import RequestFactory, SimpleTestCase, TestCase
from django.utils import timezone
from identity.models import User
from records.models import Blob, Content, Incident, MailEvent, Message

from records.ui_filters import period_bounds, resolve_period


class GlobalPeriodTests(SimpleTestCase):
    def request(self, query='', session=None):
        request = RequestFactory().get('/overview/' + query)
        request.session = session if session is not None else {}
        return request

    def test_session_and_explicit_priority(self):
        request = self.request('?range=168&q=keep&page=3')
        self.assertEqual(resolve_period(request)['range'], '168')
        self.assertEqual(request.GET['q'], 'keep')
        for path in ('/incidents/', '/messages/', '/analytics/'):
            following = RequestFactory().get(path)
            following.session = request.session
            self.assertEqual(resolve_period(following)['range'], '168')
        override = self.request('?range=720', request.session)
        self.assertEqual(resolve_period(override)['range'], '720')

    def test_invalid_custom_never_replaces_session(self):
        for query in ('?range=custom&start=bad', '?range=custom&start=2026-01-01T12:00',
                      '?range=custom&start=2026-01-02T12:00&end=2026-01-01T12:00'):
            request = self.request(query, {'mice_period': {'range': '168'}})
            self.assertEqual(resolve_period(request)['range'], '168')
            self.assertEqual(request.session['mice_period'], {'range': '168'})

    def test_dst_offsets_and_poll_does_not_overwrite(self):
        request = self.request('?range=custom&start=2026-03-08T01:00&end=2026-03-08T04:00&start_offset=-300&end_offset=-240')
        dates = resolve_period(request)
        start, end = period_bounds(dates)
        self.assertEqual(end - start, timedelta(hours=2))
        poll = self.request('?range=24', {'mice_period': {'range': '168'}})
        poll.META['HTTP_X_MICE_PERIOD_POLL'] = 'true'
        resolve_period(poll)
        self.assertEqual(poll.session['mice_period']['range'], '168')


class PeriodPageTests(TestCase):
    def test_all_four_pages_really_filter_by_saved_period(self):
        user = User.objects.create_superuser('period-admin', 'test-password-long')
        self.client.force_login(user)
        session = self.client.session
        session['mice_access_version'] = user.access_version
        session.save()
        for days in (2, 12):
            blob = Blob.objects.create(sha=str(days) * 32, data=b'mail', size=4)
            message = Message.objects.create(original_sha_ref=blob, format='eml', status='ANALYZED',
                                             created_at=timezone.now() - timedelta(days=days))
            event = MailEvent.objects.create(message=message, source='test', source_key=str(days))
            Incident.objects.create(message=message, event=event, risk=70,
                                    created_at=message.created_at, findings=[], policy_hits=[])
        overview = self.client.get('/overview/?range=168')
        self.assertEqual(overview.context['analytics_total'], 1)
        self.assertEqual(self.client.get('/incidents/').context['page'].paginator.count, 1)
        self.assertEqual(self.client.get('/messages/').context['page'].paginator.count, 1)
        self.assertEqual(self.client.get('/analytics/').context['analytics_total'], 1)
        self.assertEqual(self.client.get('/analytics/').context['analytics_total'], 1)
        self.assertEqual(self.client.get('/analytics/?export=timeline')['Content-Type'], 'text/csv; charset=utf-8')
        self.assertEqual(self.client.get('/incidents/?range=720').context['page'].paginator.count, 2)
    def test_risk_drilldown_and_incomplete_mail_counter(self):
        user = User.objects.create_superuser('risk-admin', 'test-password-long')
        self.client.force_login(user)
        session = self.client.session
        session['mice_access_version'] = user.access_version
        session.save()
        for risk, state in ((99, 'ANALYZED'), (0, 'PARTIAL'), (98, 'FAILED')):
            blob = Blob.objects.create(sha=f'{risk:064x}', data=b'mail', size=4)
            message = Message.objects.create(original_sha_ref=blob, format='eml', status=state)
            event = MailEvent.objects.create(message=message, source='test', source_key=str(risk))
            Incident.objects.create(message=message, event=event, risk=risk, findings=[], policy_hits=[])
        overview = self.client.get('/overview/?range=24')
        self.assertContains(overview, 'hx-boost="false" class="so-risk-line')
        self.assertContains(overview, 'severity=high&amp;status=')
        self.assertEqual(overview.context['analytics_incomplete'], 2)
        self.assertEqual(self.client.get('/incidents/?range=24&severity=high&status=').context['page'].paginator.count, 2)
        self.assertEqual(self.client.get('/messages/?range=24&status=INCOMPLETE').context['page'].paginator.count, 2)
