import copy
import hashlib
import json
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase, TestCase

from app.categories import evaluate_groups
from app.detection_evidence import analyze
from app.detectors import detect, inn_valid
from app.evidence import evidence_count, normalized_variant, unique_findings
from app.text_match import search
from policy_engine.restoration import load_configuration, restore
from policy_engine.ru3 import candidate, upgrade
from policy_engine.rules import policy_matches
from records.models import Audit, Category, CategoryRule, Policy, Setting


def group(mode="any", **config):
    rule = SimpleNamespace(id="rule", kind="keywords", title="Test", risk=70,
                           config={"phrases": ["секрет"], **config}, enabled=True)
    category = SimpleNamespace(id="custom", name="Test", mode="custom", match_mode=mode, active=True)
    return {"category": category, "rules": [rule]}


class EngineRU3Tests(SimpleTestCase):
    def test_local_exclusion_does_not_hide_independent_hit(self):
        text = "секрет учебный пример " + "нейтральный " * 40 + "секрет клиента"
        hits = search(text, phrases=["секрет"], exclude_phrases=["учебный пример"])
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0][0], text.rfind("секрет"))
        self.assertEqual(len(evaluate_groups([group(exclude_phrases=["учебный пример"])], text)), 1)

    def test_repeated_literals_and_morphology_are_independent(self):
        for mode in ("substring", "word", "morphology"):
            self.assertEqual(len(search("секрет " + "слово " * 20 + "секрет", mode=mode, phrases=["секрет"])), 2)

    def test_weight_required_order_window_and_unique_count(self):
        terms = [{"text": "бюджет", "weight": 3, "required": True},
                 {"text": "закрытый", "weight": 5, "required": False}]
        args = dict(mode="flexible", terms=terms, min_score=8, window=4)
        self.assertFalse(search("закрытый закрытый", **args))
        self.assertFalse(search("бюджет бюджет бюджет", **args))
        self.assertTrue(search("бюджеты закрытые", **args))
        self.assertFalse(search("бюджет " + "слово " * 8 + "закрытый", **args))
        self.assertFalse(search("закрытый бюджет", ordered=True, **args))
        self.assertTrue(search("бюджет закрытый", ordered=True, **args))
        self.assertEqual(len(search("бюджет закрытый бюджет закрытый", **args)), 2)

    def test_normalization_source_mapping_and_identifiers(self):
        text = "ﬀ с\u200bекpет 7707083893 паспорт 123456"
        variant, spans, transforms = normalized_variant(text, "medium")
        self.assertIn("секрет", variant)
        self.assertIn("7707083893", variant)
        self.assertIn("123456", variant)
        hits = evaluate_groups([group()], text, normalized=(variant, spans, transforms))
        self.assertEqual(len(hits), 1)
        hit = hits[0]
        self.assertEqual(text[hit["start"]:hit["end"]], "с\u200bекpет")
        self.assertEqual(hit["original_excerpt"], "с\u200bекpет")
        self.assertIn("invisible_characters", hit["normalization"])

    def test_normalization_does_not_duplicate_original(self):
        text = "секрет \u200b"
        hits = evaluate_groups([group()], text, normalized=normalized_variant(text, "medium"))
        self.assertEqual(len(unique_findings(hits)), 1)

    def test_high_normalization_and_safe_regex(self):
        from app.evidence import normalization_safe_regex
        text = "с-е-к-р-е-т 1234567890"
        variant, spans, transforms = normalized_variant(text, "high")
        self.assertEqual(variant, "секрет 1234567890")
        self.assertEqual(spans[5][1], len("с-е-к-р-е-т"))
        self.assertIn("separated_letters", transforms)
        self.assertTrue(normalization_safe_regex("секрет"))
        self.assertFalse(normalization_safe_regex(r"\d{10}"))

    def test_contained_detector_evidence_keeps_provenance(self):
        a = dict(category="custom", risk=70, start=5, end=10, rule_id="a", source="custom-keywords")
        b = dict(a, start=2, end=14, rule_id="b", risk=80)
        hits = unique_findings([a, b, dict(a, start=30, end=35)])
        self.assertEqual(len(hits), 2)
        self.assertEqual(hits[0]["risk"], 80)
        self.assertEqual(len(hits[0]["supporting_rules"]), 2)

    def test_disabled_category_rule_and_all(self):
        bucket = group(mode="all")
        missing = copy.copy(bucket["rules"][0])
        missing.id, missing.config = "missing", {"phrases": ["нет"]}
        bucket["rules"].append(missing)
        self.assertFalse(evaluate_groups([bucket], "секрет"))
        missing.enabled = False
        self.assertTrue(evaluate_groups([bucket], "секрет"))
        bucket["category"].active = False
        self.assertFalse(evaluate_groups([bucket], "секрет"))

    def test_unique_policy_count_retains_category_all(self):
        hits = [dict(category=c, risk=70, start=3, end=9, source=s, rule_id=s)
                for c, s in (("INN", "a"), ("RU_INN", "b"), ("OTHER", "c"))]
        self.assertEqual(evidence_count(unique_findings(hits)), 1)
        self.assertFalse(policy_matches(hits, {"min_count": 2}))
        self.assertTrue(policy_matches(hits, {"categories": ["INN", "OTHER"], "category_match": "all"}))
        hits.append(dict(hits[0], start=20, end=26))
        self.assertTrue(policy_matches(hits, {"min_count": 2}))

    def test_code_risk_requires_confidential_transfer_context(self):
        for text, expected in [("def example():", 15),
                               ("Учебный исходный код\ndef example():", 15),
                               ("Передаю конфиденциальный исходный код\ndef internal():", 65),
                               ("Конфиденциально " + "слово " * 150 + "def example():", None)]:
            hits = [h for h in detect(text) if h["category"] == "CODE"]
            if expected is not None:
                self.assertEqual(hits[0]["risk"], expected)
        self.assertFalse(policy_matches(detect("def example():"), {"categories": ["CODE"], "min_risk": 60}))

    def test_canonical_inn_and_phone_checksum_unchanged(self):
        self.assertTrue(inn_valid("7707083893"))
        self.assertFalse(inn_valid("7707083894"))
        hits = detect("7707083893 7707083894 +7 (999) 123-45-67")
        self.assertEqual([h["category"] for h in hits], ["PHONE", "INN"])

    @patch("app.advanced_detectors.pii", return_value=[])
    def test_document_boundaries_and_normalizer_switch(self, pii):
        bucket = group(mode="all", match_type="flexible", phrases=[], terms=[
            {"text": "секрет", "weight": 4, "required": True},
            {"text": "клиент", "weight": 4, "required": True}], min_score=8)
        config = {"settings": {}, "references": [], "groups": [{
            "category": vars(bucket["category"]), "rules": [vars(r) for r in bucket["rules"]]}]}
        payload = {"text": "секрет клиент", "configuration": config, "attachments": [],
                   "documents": [{"id": "body", "text": "секрет"}, {"id": "file", "text": "клиент"}]}
        self.assertFalse(analyze(payload)["findings"])
        config["groups"][0]["rules"][0]["config"] = {"phrases": ["секрет"]}
        payload["documents"] = [{"id": "body", "text": "с\u200bекpет"}]
        self.assertFalse(analyze(payload)["findings"])
        config["settings"]["normalizer"] = {"enabled": True}
        self.assertEqual(len(analyze(payload)["findings"]), 1)
        config["settings"]["detectors"] = {"normalizer": False, "pii": False}
        self.assertFalse(analyze(payload)["findings"])
        pii.reset_mock()
        analyze(payload)
        pii.assert_not_called()


class RU3UpgradeTests(TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)

    def test_upgrade_archive_backup_and_idempotence(self):
        restore(load_configuration())
        old = list(CategoryRule.objects.values())
        policy = Policy.objects.first()
        policy.enabled = True
        policy.save()
        report = upgrade(backup_dir=self.directory.name, apply=True)
        data = Path(report["backup"]).read_bytes()
        self.assertEqual(hashlib.sha256(data).hexdigest(), report["backup_sha256"])
        self.assertEqual(len(json.loads(data)["rules"]), 33)
        self.assertEqual(CategoryRule.objects.count(), 38)
        self.assertEqual(CategoryRule.all_objects.filter(deleted_at__isnull=False).count(), 33)
        for original in old:
            archived = CategoryRule.all_objects.get(pk=original["id"])
            self.assertEqual(archived.config, original["config"])
            self.assertEqual(archived.title, original["title"])
        policy.refresh_from_db()
        self.assertTrue(policy.enabled)
        before = list(Policy.objects.order_by("pk").values())
        self.assertTrue(upgrade(backup_dir=self.directory.name, apply=True)["already_applied"])
        self.assertEqual(before, list(Policy.objects.order_by("pk").values()))
        self.assertEqual(Audit.objects.filter(action="dlp_ru3_upgrade").count(), 1)
        with self.assertRaises(ValueError):
            restore(load_configuration())

    def test_backup_failure_leaves_configuration_unchanged(self):
        restore(load_configuration())
        before = list(CategoryRule.objects.order_by("pk").values())
        with patch("policy_engine.ru3.write_backup", side_effect=OSError("read-only")):
            with self.assertRaises(OSError):
                upgrade(backup_dir=self.directory.name, apply=True)
        self.assertEqual(before, list(CategoryRule.objects.order_by("pk").values()))
        self.assertFalse(Setting.objects.filter(pk="dlp_rulepack").exists())

    def test_mid_update_failure_rolls_back_and_keeps_backup(self):
        restore(load_configuration())
        before = list(CategoryRule.objects.order_by("pk").values())
        with patch("policy_engine.ru3.revision", side_effect=ValueError("forced failure")):
            with self.assertRaises(ValueError):
                upgrade(backup_dir=self.directory.name, apply=True)
        self.assertEqual(before, list(CategoryRule.objects.order_by("pk").values()))
        self.assertFalse(Setting.objects.filter(pk="dlp_rulepack").exists())
        self.assertTrue(list(Path(self.directory.name).glob("*.json")))

    def test_new_install_and_candidate_validation(self):
        pack, rules, _ = candidate()
        self.assertEqual(len(rules), 38)
        upgrade(backup_dir=self.directory.name, apply=True)
        self.assertEqual(Policy.objects.count(), 8)
        self.assertFalse(Policy.objects.filter(enabled=True).exists())
        self.assertEqual(CategoryRule.objects.count(), 38)
        self.assertEqual(Category.objects.filter(pk__in=[c["id"] for c in pack["categories"]]).count(), 12)

    def test_all_weighted_rules_reach_threshold_and_policy_risk(self):
        from app.text_match import tokens
        pack, rules, _ = candidate()
        policies = {c: p["min_risk"] for p in pack["policies"] for c in p["categories"]}
        for rule in rules:
            self.assertGreaterEqual(rule["risk"], policies[rule["category_id"]], rule["title"])
            config = rule["config"]
            if config.get("match_type") != "flexible":
                continue
            terms = config["terms"]
            # Morphological aliases in the prepared dictionary must contribute
            # once, not inflate the score for one lexical occurrence.
            text = " ".join(term["text"] for term in terms)
            options = {k: v for k, v in config.items() if k != "match_type"}
            self.assertTrue(search(text, mode="flexible", **options), rule["title"])

    def test_history_archive_and_ru2_import_guard(self):
        from policy_engine.rulepacks import apply, parse
        from policy_engine.templatetags.evidence_history import historical_findings
        from records.models import Blob, Content, Message
        restore(load_configuration())
        old = CategoryRule.objects.first()
        blob = Blob.objects.create(sha="b"*64, data=b"history", size=7)
        content = Content.objects.create(normalized_sha="c"*64, text="history", analysis={})
        message = Message.objects.create(original_sha_ref=blob, content=content, format="eml")
        upgrade(backup_dir=self.directory.name, apply=True)
        shown = historical_findings({"message": message}, [{"rule_id": old.pk, "category": old.category_id}])[0]
        self.assertEqual(shown["historical_rule"]["config"], old.config)
        self.assertEqual(shown["historical_rule"]["title"], old.title)
        self.assertTrue(shown["rule_deleted"])
        raw = (Path(__file__).resolve().parents[1] / "config/rulepacks/ru2_morph_weighted_rules.json").read_bytes()
        with self.assertRaises(ValueError):
            apply(parse(raw), SimpleNamespace(pk="test"), update=True)