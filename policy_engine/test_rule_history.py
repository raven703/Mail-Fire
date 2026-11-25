from types import SimpleNamespace

from django.test import TestCase

from app.categories import evaluate_groups
from identity.models import User
from pipeline.evidence import configuration
from policy_engine.category_pages import CategoryForm, category_rules, save_category
from policy_engine.templatetags.evidence_history import historical_findings
from records.models import Audit, Blob, Category, CategoryRule, Content, Incident, MailEvent, Message


class RuleHistoryTests(TestCase):
    def setUp(self):
        self.actor = User.objects.create_superuser('history-admin', 'test-password-long')
        self.category = Category.objects.create(pk='history-category', name='Историческая категория', mode='custom', match_mode='all')
        self.first = CategoryRule.objects.create(category=self.category, kind='keywords', title='Первое правило',
                                                config={'phrases': ['secret'], 'match_type': 'substring'})
        self.second = CategoryRule.objects.create(category=self.category, kind='keywords', title='Второе правило',
                                                 config={'phrases': ['missing'], 'match_type': 'substring'})

    def forms(self, delete=()):
        form = CategoryForm({'name': self.category.name, 'group_name': 'Группа', 'mode': 'custom',
                             'match_mode': 'all', 'active': 'on', 'description': 'Описание'}, instance=self.category)
        data = {'rules-TOTAL_FORMS': '2', 'rules-INITIAL_FORMS': '2'}
        for i, rule in enumerate((self.first, self.second)):
            for key, value in {'id': rule.pk, 'title': rule.title, 'kind': rule.kind, 'risk': rule.risk,
                               'priority': rule.priority, 'enabled': 'on',
                               'phrases': '\n'.join(rule.config['phrases']), 'match_type': 'substring'}.items():
                data[f'rules-{i}-{key}'] = value
            if rule.pk in delete:
                data[f'rules-{i}-DELETE'] = 'on'
        return form, category_rules(data, self.category)

    def test_delete_is_deferred_audited_and_keeps_history(self):
        snapshot = configuration()
        finding = {'rule_id': self.second.pk, 'category': self.category.pk, 'risk': 70, 'reason': 'Original reason'}
        content = Content.objects.create(normalized_sha='h' * 64, text='secret', version='v1',
                                         analysis={'findings': [finding], 'configuration_snapshot': snapshot})
        blob = Blob.objects.create(sha='b' * 64, data=b'mail', size=4)
        message = Message.objects.create(original_sha_ref=blob, format='eml', content=content)
        event = MailEvent.objects.create(message=message, source='test', source_key='history-event')
        incident = Incident.objects.create(message=message, event=event, findings=[finding], policy_hits=[])
        form, rules = self.forms(delete=[self.second.pk])
        self.assertTrue(form.is_valid(), form.errors)
        self.assertTrue(rules.is_valid(), rules.errors)
        self.assertTrue(CategoryRule.objects.filter(pk=self.second.pk).exists())
        save_category(self.actor, form, rules)
        self.assertFalse(CategoryRule.objects.filter(pk=self.second.pk).exists())
        self.assertTrue(CategoryRule.all_objects.get(pk=self.second.pk).deleted_at)
        self.assertTrue(Audit.objects.filter(action='rule_delete', target=self.second.pk).exists())
        historical = historical_findings({'message': message}, [finding])[0]
        self.assertTrue(historical['rule_deleted'])
        self.assertEqual(historical['historical_rule']['title'], 'Второе правило')
        self.assertEqual(historical['historical_rule']['config'], self.second.config)
        self.assertEqual(Content.objects.get(pk=content.pk).analysis['findings'], [finding])
        incident.refresh_from_db()
        self.assertEqual(incident.findings, [finding])
        self.assertTrue(historical_findings({'incident': incident}, incident.findings)[0]['rule_deleted'])
        self.assertEqual(len(category_rules(None, self.category).forms), 1)

    def test_any_all_use_only_live_rules_and_empty_active_category_rejected(self):
        def hits():
            groups = [{'category': SimpleNamespace(**g['category']),
                       'rules': [SimpleNamespace(**r) for r in g['rules']]}
                      for g in configuration()['groups']]
            return evaluate_groups(groups, 'secret')
        self.assertFalse(hits())
        self.category.match_mode = 'any'
        self.category.save()
        self.assertTrue(hits())
        self.category.match_mode = 'all'
        self.category.save()
        form, rules = self.forms(delete=[self.first.pk, self.second.pk])
        self.assertFalse(rules.is_valid())
        self.assertIn('включённое правило', str(rules.non_form_errors()))
        form, rules = self.forms(delete=[self.second.pk])
        self.assertTrue(form.is_valid())
        self.assertTrue(rules.is_valid())
        save_category(self.actor, form, rules)
        self.assertTrue(hits())

    def test_edits_never_replace_saved_metadata(self):
        finding = {'rule_id': self.first.pk, 'historical_rule': {'title': 'Original', 'kind': 'keywords',
                   'config': {'phrases': ['original']}}, 'risk': 70}
        self.first.title = 'Changed'
        self.first.save()
        self.assertEqual(historical_findings({}, [finding])[0]['historical_rule']['title'], 'Original')
        self.assertEqual(len(category_rules(None, self.category).forms), 2)
        self.assertEqual(len(category_rules(None).forms), 0)