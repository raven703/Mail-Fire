from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase, SimpleTestCase, override_settings
from django.utils import timezone
from identity.models import User
from records.models import Setting, OCRTestDocument, Message, Incident, TrainingExample
from records.ocr_settings import configuration, purge, document_for
from pipeline.parser_client import call


class OCRSettingsTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser('ocr-admin', 'long-test-password')
        self.client.force_login(self.user)
        session = self.client.session
        session['mice_access_version'] = self.user.access_version
        session.save()

    @patch('records.ocr_settings.availability', return_value={'provider': 'rapidocr', 'available': True})
    def test_configuration_persists_and_defaults_to_rapid(self, available):
        self.assertEqual(configuration()['provider'], 'rapidocr')
        response = self.client.post('/settings/ocr/', {'action': 'save', 'enabled': 'on', 'provider': 'surya'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(configuration(), {'enabled': True, 'provider': 'surya'})
        self.assertEqual(Setting.objects.get(pk='ocr').value['provider'], 'surya')
        self.client.post('/settings/ocr/', {'action': 'save', 'provider': 'paddleocr'})
        self.assertFalse(configuration()['enabled'])
        self.assertEqual(self.client.get('/settings/ocr/').status_code, 200)

    @patch('records.ocr_settings.availability', return_value={'provider': 'surya', 'available': False})
    def test_invalid_provider_not_saved(self, available):
        response = self.client.post('/settings/ocr/', {'action': 'save', 'provider': 'external'})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Setting.objects.filter(pk='ocr').exists())

    def test_expired_documents_are_removed(self):
        OCRTestDocument.objects.create(owner=str(self.user.pk), data=b'private', name='document.png', expires_at=timezone.now()-timedelta(seconds=1))
        purge()
        self.assertEqual(OCRTestDocument.objects.count(), 0)

    def test_preview_token_is_required(self):
        self.assertEqual(self.client.get('/settings/ocr/preview/?token=invalid').status_code, 404)

    @patch('records.ocr_settings.availability', return_value={'provider': 'rapidocr', 'available': True})
    @patch('records.ocr_settings.call')
    def test_manual_upload_and_reuse_do_not_create_mail(self, parser, available):
        from django.core.files.uploadedfile import SimpleUploadedFile
        parser.return_value = {'image': '', 'text': 'test', 'status': 'ANALYZED', 'details': {'pages': 1, 'ocr': []}}
        response = self.client.post('/settings/ocr/', {'action': 'test', 'provider': 'rapidocr', 'document': SimpleUploadedFile('a.png', b'png'), 'force_ocr': 'on'})
        token = response.context['token']
        self.assertEqual(OCRTestDocument.objects.count(), 1)
        response = self.client.post('/settings/ocr/', {'action': 'test', 'provider': 'surya', 'token': token, 'force_ocr': 'on'})
        self.assertEqual(response.context['result']['text'], 'test')
        self.assertEqual(parser.call_args.kwargs['provider'], 'surya')
        self.assertTrue(parser.call_args.kwargs['force_ocr'])
        self.assertEqual(Message.objects.count()+Incident.objects.count()+TrainingExample.objects.count(), 0)

    def test_unauthenticated_access_is_denied(self):
        self.client.logout()
        self.assertIn(self.client.get('/settings/ocr/').status_code, (302, 403))


class OCRRoutingTests(SimpleTestCase):
    @override_settings(MICE_SURYA_URL='http://surya:8090')
    @patch('pipeline.parser_client.httpx.Client')
    def test_explicit_surya_route_does_not_read_database(self, client):
        response = client.return_value.__enter__.return_value.stream.return_value.__enter__.return_value
        response.iter_bytes.return_value = [b'{"text":"ok"}']
        client.return_value.__enter__.return_value.stream.return_value.__enter__.return_value.status_code = 200
        self.assertEqual(call('extract', b'png', 'test.png', ocr=True, provider='surya')['text'], 'ok')
        arguments = client.return_value.__enter__.return_value.stream.call_args
        self.assertEqual(arguments.args[1], 'http://surya:8090/parse')
        self.assertEqual(arguments.kwargs['json']['provider'], 'surya')

    def test_invalid_explicit_provider_is_rejected(self):
        with self.assertRaises(ValueError):
            call('extract', b'png', ocr=True, provider='unknown')
