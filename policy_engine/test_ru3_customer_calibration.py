import json
from pathlib import Path
from django.test import SimpleTestCase
from app.text_match import search

ROOT = Path(__file__).resolve().parents[1]


class RU3CustomerCalibrationTests(SimpleTestCase):
    def test_examples(self):
        pack = json.loads((ROOT / "config/rulepacks/ru3_candidate.json").read_text())
        cat = next(c for c in pack["categories"] if c["id"] == "pack-ru2-customer-data")
        metadata = {"kind", "title", "enabled", "risk", "priority"}
        examples = [
            (True, "Закрытая клиентская база передана на проверку."),
            (True, "Клиентская база включает историю заказов."),
            (True, "Просим экспортировать базу клиентов в CSV."),
            (True, "Выгрузите реестр клиентов с телефонами."),
            (True, "Экспорт CRM содержит контакты покупателей."),
            (False, "Установили обновление CRM."),
            (False, "Клиентская база увеличилась за квартал."),
            (False, "Выгрузка персональных данных работников."),
            (False, "Передача реестра оборудования."),
            (False, "Просим связаться с покупателем по телефону."),
        ]
        for expected, text in examples:
            with self.subTest(text=text):
                actual = False
                for rule in cat["rules"]:
                    config = {k:v for k,v in rule.items() if k not in metadata}
                    mode = config.pop("match_type")
                    actual |= bool(search(text, mode=mode, **config))
                self.assertEqual(expected, actual)
