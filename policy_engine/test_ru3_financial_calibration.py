import json
from pathlib import Path
from django.test import SimpleTestCase
from app.text_match import search

ROOT = Path(__file__).resolve().parents[1]


class RU3FinancialCalibrationTests(SimpleTestCase):
    def test_examples(self):
        pack = json.loads((ROOT / "config/rulepacks/ru3_candidate.json").read_text())
        cat = next(c for c in pack["categories"] if c["id"] == "pack-ru2-financial-plans")
        metadata = {"kind", "title", "enabled", "risk", "priority"}
        examples = [
            (True, "Конфиденциальный бюджет филиала на следующий год."),
            (True, "Внутренний прогноз выручки подготовлен для совета директоров."),
            (True, "Черновой бюджет отдела. Запрещено внешнее распространение."),
            (True, "Внутренний финансовый прогноз передан руководству."),
            (False, "Утвердите бюджет муниципального проекта."),
            (False, "Опубликован бюджет города. Закрытых прогнозов здесь нет."),
            (False, "Прогноз выручки на квартал опубликован в открытом отчете."),
            (False, "Согласуйте плановую маржинальность по публичному тарифу."),
        ]
        for expected, text in examples:
            with self.subTest(text=text):
                actual = False
                for rule in cat["rules"]:
                    config = {k:v for k,v in rule.items() if k not in metadata}
                    mode = config.pop("match_type")
                    actual |= bool(search(text, mode=mode, **config))
                self.assertEqual(expected, actual)
