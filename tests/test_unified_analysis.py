"""Run in a Linux parser image, not in the secret-bearing Django worker."""
import base64
import concurrent.futures
import os
import socket
import tempfile
from email.message import EmailMessage
from pathlib import Path
from unittest.mock import patch

from app.unified_analysis import analyze_message


def mail_payload(subject="test", with_image=True):
    message = EmailMessage()
    message["Subject"] = subject
    message.set_content("body")
    message.add_attachment(b"native", maintype="text", subtype="plain", filename="note.txt")
    if with_image:
        message.add_attachment(b"image", maintype="image", subtype="png", filename="image.png")
    return {"original": base64.b64encode(message.as_bytes()).decode(),
            "configuration": {"settings": {"detectors": {"static_files": False, "secrets": False}},
                              "groups": [], "references": []}, "ocr_enabled": with_image}


def test_mail_native_and_ocr_documents_are_separate():
    ocr = lambda data, name: {"text": "recognized", "status": "ANALYZED", "details": {}}
    with patch("app.detection_evidence.analyze", return_value={"findings": [], "version": "test",
               "engine_errors": [], "skipped_checks": [], "normalization": {}}) as evidence:
        result = analyze_message(mail_payload(), ocr)
    documents = evidence.call_args.args[0]["documents"]
    assert [d["text"].strip() for d in documents] == ["body", "native", "recognized"]
    assert len(result["attachments"]) == 2
    assert result["attachments"][1]["status"] == "ANALYZED"


def test_real_fork_broker_parallel_requests_and_ocr_relay():
    from app.analysis_broker import AnalysisBroker
    broker = AnalysisBroker()
    try:
        with patch.object(broker, "ocr", return_value={"text": "recognized", "status": "ANALYZED", "details": {}}):
            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
                results = list(pool.map(broker.analyze, [mail_payload("first"), mail_payload("second", False)]))
        assert [r["parsed"]["subject"] for r in results] == ["first", "second"]
        assert results[0]["attachments"][1]["text"] == "recognized"
        assert len(results[1]["attachments"]) == 1
        assert results[0]["attachments"][0]["id"] != results[1]["attachments"][0]["id"]
    finally:
        broker.close()


def test_filesystem_and_network_confinement():
    from app.analysis_isolation import confine
    from app.sandbox import restrict
    with tempfile.TemporaryDirectory() as own, tempfile.TemporaryDirectory() as sibling:
        secret = Path(sibling) / "marker"
        secret.write_text("private")
        pid = os.fork()
        if pid == 0:
            try:
                os.chdir(own)
                os.environ["TMPDIR"] = own
                tempfile.tempdir = own
                confine(own)
                restrict(scan=True, unified=True)
                Path(own, "allowed").write_text("ok")
                try:
                    secret.read_text()
                except PermissionError:
                    pass
                else:
                    os._exit(2)
                try:
                    socket.socket()
                except PermissionError:
                    pass
                else:
                    os._exit(3)
                os._exit(0)
            except BaseException:
                os._exit(4)
        _, status = os.waitpid(pid, 0)
        assert os.waitstatus_to_exitcode(status) == 0
