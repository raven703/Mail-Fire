"""Offline tests, no model download or working application imports."""
# ruff: noqa: E402 -- standalone directory is deliberately not an application package
import json
import sys
from email.message import EmailMessage
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from prepare import extract, windows
from run import verify_frozen
from summarize import metric


def test_no_window_gaps():
    text = "abcdefg" * 1000
    chunks = list(windows(text))
    covered = set()
    for start, chunk in chunks:
        assert chunk == text[start:start + len(chunk)]
        covered.update(range(start, start + len(chunk)))
    assert covered == set(range(len(text)))


def test_mime_body_attachment_and_offsets():
    msg = EmailMessage()
    msg["Subject"] = "Тема"
    msg.set_content("Обычное тело письма")
    msg.add_attachment("Закрытый бюджет", filename="test.txt")
    result = extract(msg.as_bytes())
    assert not result["extraction_errors"]
    assert "Закрытый бюджет" in result["text"]
    assert {s["source"] for s in result["segments"]} == {"subject", "body", "attachment"}
    for segment in result["segments"]:
        assert result["text"][segment["start"]:segment["end"]] == segment["text"]


def test_alternative_not_duplicated():
    msg = EmailMessage()
    msg.set_content("plain")
    msg.add_alternative("<p>html alternative</p>", subtype="html")
    result = extract(msg.as_bytes())
    assert "plain" in result["text"] and "html alternative" not in result["text"]


def test_metrics():
    assert metric(2, 1, 1, 3)["f1"] == 2 / 3
    assert metric(0, 0, 1)["precision"] == 0


def test_inputs_and_cohorts_frozen():
    frozen = verify_frozen()
    assert len(frozen["classification"]) == 350
    assert len(set(frozen["classification"])) == 350
    assert frozen["classification"] == frozen["ner_qualitative"]


def test_fixture_spans_unambiguous():
    fixture = json.loads((HERE / "ner_fixture.json").read_text())
    assert "NOT independently" in fixture["annotation_status"]
    for row in fixture["examples"]:
        for _, value in row["entities"]:
            assert row["text"].count(value) == 1