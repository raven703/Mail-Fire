import json
from pathlib import Path
from django.test import SimpleTestCase
from app.text_match import search

ROOT = Path(__file__).resolve().parents[1]


class RU3PricingCalibrationTests(SimpleTestCase):
    def test_examples(self):
        pack = json.loads((ROOT / "config/rulepacks/ru3_candidate.json").read_text())
        cat = next(c for c in pack["categories"] if c["id"] == "pack-ru2-pricing")
        metadata = {"kind", "title", "enabled", "risk", "priority"}
        examples = [
            (True, "Согласуйте индивидуальную скидку покупателю на партию товара."),
            (True, "Закрытые закупочные цены на комплектующие."),
            (True, "В таблице непубличные расценки подрядчиков."),
            (True, "Себестоимость изделия и наценка указаны в расчете."),
            (True, "Конфиденциальная скидка на обслуживание."),
            (False, "Индивидуальные условия и скидки не обсуждаются."),
            (False, "Публичный прайс доступен на сайте."),
            (False, "Скидки на все товары по акции."),
            (False, "Обсудили себестоимость проекта."),
            (False, "Внутренний регламент описывает порядок объявления скидок."),
        ]
        for expected, text in examples:
            with self.subTest(text=text):
                actual = False
                for rule in cat["rules"]:
                    config = {k:v for k,v in rule.items() if k not in metadata}
                    mode = config.pop("match_type")
                    actual |= bool(search(text, mode=mode, **config))
                self.assertEqual(expected, actual)
