import json
from pathlib import Path
from django.test import SimpleTestCase
from app.text_match import search

ROOT = Path(__file__).resolve().parents[1]


class RU3PIICalibrationTests(SimpleTestCase):
    def test_examples(self):
        pack = json.loads((ROOT / "config/rulepacks/ru3_candidate.json").read_text())
        cat = next(c for c in pack["categories"] if c["id"] == "pack-ru2-pii-handling")
        metadata = {"kind", "title", "enabled", "risk", "priority"}
        examples = [
            (True, "Передайте личные данные заявителя в отдел кадров."),
            (True, "Просим направить персональные сведения получателя ответственному сотруднику."),
            (True, "Отправьте скан паспорта заявителя."),
            (True, "Выгрузка персональных сведений участников."),
            (True, "Необходимо переслать персональные данные участников комиссии."),
            (False, "Запрос копии паспорта сотрудника рассмотрен."),
            (False, "Копия паспорта сотрудника имеется в архиве."),
            (False, "Скан паспорта хранится в личном деле."),
            (False, "Личные данные обрабатываются в соответствии с регламентом."),
            (False, "Персональные сведения доступны ответственному сотруднику."),
            (False, "Отправьте пустой бланк заявления."),
        ]
        for expected, text in examples:
            with self.subTest(text=text):
                actual = False
                for rule in cat["rules"]:
                    config = {k:v for k,v in rule.items() if k not in metadata}
                    mode = config.pop("match_type")
                    actual |= bool(search(text, mode=mode, **config))
                self.assertEqual(expected, actual)
