"""Prepare fresh plain-text observations using native MIME parser, no OCR or detection."""
import argparse, hashlib, json, sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from app.mail import parse_mail
p=argparse.ArgumentParser()
p.add_argument("--output",type=Path,required=True)
a=p.parse_args()
root=Path(__file__).resolve().parent
with a.output.open("x",encoding="utf-8") as out:
    for line in (root/"manifest.jsonl").read_text(encoding="utf-8").splitlines():
        case=json.loads(line)
        raw=(root/case["file"]).read_bytes()
        parsed=parse_mail(raw)
        assert not parsed["attachments"]
        row=dict(id=case["id"],sha256=hashlib.sha256(raw).hexdigest(),status="ANALYZED",text=parsed["text"],attachments=[],analysis={"findings":[]})
        out.write(json.dumps(row,ensure_ascii=False)+"\n")
