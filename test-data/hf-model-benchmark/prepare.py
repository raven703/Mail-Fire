"""Standalone MIME extraction; never imports MICE, detector outputs or gold text hints."""
import csv
import hashlib
import io
import json
import re
import shutil
import zipfile
from collections import Counter
from email import policy
from email.parser import BytesParser
from pathlib import Path
from xml.etree import ElementTree as ET

HERE = Path(__file__).resolve().parent
CORPUS = HERE.parent / "benchmark-350-v1"


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def write_json(path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def decode(raw, charset=None):
    for encoding in dict.fromkeys([charset or "utf-8", "utf-8-sig", "cp1251"]):
        try:
            return raw.decode(encoding)
        except (UnicodeError, LookupError):
            continue
    raise ValueError("Text decoding failed; no silent replacement")


def html_text(text):
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(text, "html.parser")
    for node in soup(["script", "style"]):
        node.decompose()
    return soup.get_text(" ", strip=True)


def attachment_text(raw, name, content_type):
    suffix = Path(name).suffix.lower()
    if suffix == ".docx":
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            doc = ET.fromstring(archive.read("word/document.xml"))
            ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
            return "\n".join("".join(p.itertext()) for p in doc.findall(".//w:p", ns))
    if suffix == ".xlsx":
        ns = {"s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            shared = []
            if "xl/sharedStrings.xml" in archive.namelist():
                shared = ["".join(n.itertext()) for n in ET.fromstring(archive.read("xl/sharedStrings.xml")).findall("s:si", ns)]
            lines = []
            for filename in sorted(archive.namelist()):
                if not re.fullmatch(r"xl/worksheets/sheet\d+\.xml", filename):
                    continue
                for row in ET.fromstring(archive.read(filename)).findall(".//s:row", ns):
                    cells = []
                    for cell in row.findall("s:c", ns):
                        value = "".join(cell.itertext())
                        cells.append(shared[int(value)] if cell.get("t") == "s" else value)
                    lines.append("\t".join(cells))
            return "\n".join(lines)
    if suffix == ".pdf":
        from pypdf import PdfReader

        return "\n".join(page.extract_text() or "" for page in PdfReader(io.BytesIO(raw)).pages)
    if suffix in {".png", ".jpg", ".jpeg"}:
        if not shutil.which("tesseract"):
            raise RuntimeError("OCR unavailable: no tesseract executable; pixels not replaced by manifest hints")
        import pytesseract
        from PIL import Image

        return pytesseract.image_to_string(Image.open(io.BytesIO(raw)), lang="eng")
    if suffix in {".html", ".htm"} or content_type == "text/html":
        return html_text(decode(raw))
    if suffix == ".csv":
        return "\n".join("\t".join(row) for row in csv.reader(io.StringIO(decode(raw))))
    if suffix in {".txt", ".log"} or content_type.startswith("text/"):
        return decode(raw)
    raise ValueError(f"Unsupported attachment: {content_type} {suffix}")


def extract(raw):
    message = BytesParser(policy=policy.default).parsebytes(raw)
    segments, errors = [], []
    if message.get("subject"):
        segments.append(dict(source="subject", filename=None, text=str(message["subject"])))
    body = message.get_body(preferencelist=("plain", "html"))
    if body is not None:
        try:
            text = decode(body.get_payload(decode=True), body.get_content_charset())
            if body.get_content_type() == "text/html":
                text = html_text(text)
            segments.append(dict(source="body", filename=None, text=text))
        except Exception as exc:
            errors.append(dict(source="body", error=str(exc)))
    else:
        errors.append(dict(source="body", error="No readable MIME body"))
    for part in message.walk():
        if part.is_multipart() or not (part.get_filename() or part.get_content_disposition() == "attachment"):
            continue
        name = part.get_filename() or "unnamed"
        try:
            text = attachment_text(part.get_payload(decode=True), name, part.get_content_type())
            if not text.strip():
                raise ValueError("Empty extracted attachment text")
            segments.append(dict(source="attachment", filename=name, content_type=part.get_content_type(), text=text))
        except Exception as exc:
            errors.append(dict(source="attachment", filename=name, error=f"{type(exc).__name__}: {exc}"))
    text, offset = [], 0
    for segment in segments:
        if text:
            offset += 2
        segment.update(start=offset, end=offset + len(segment["text"]))
        offset = segment["end"]
        text.append(segment["text"])
    return dict(text="\n\n".join(text), segments=segments, extraction_errors=errors,
                mime_defects=[str(d) for part in message.walk() for d in part.defects])


def windows(text, size=900, overlap=100):
    if size <= overlap or overlap < 0:
        raise ValueError("Invalid window dimensions")
    start = 0
    while start < len(text):
        end = min(start + size, len(text))
        yield start, text[start:end]
        if end == len(text):
            break
        start = end - overlap


def main():
    results = HERE / "results"
    results.mkdir(exist_ok=True)
    prepared = results / "prepared.jsonl"
    if prepared.exists():
        raise FileExistsError("Frozen input exists; use a new checkout/output instead of overwriting")
    manifest_raw = (CORPUS / "manifest.jsonl").read_bytes()
    manifest = [json.loads(line) for line in manifest_raw.decode().splitlines()]
    sources, extraction = {}, []
    with prepared.open("x", encoding="utf-8") as output:
        for row in manifest:
            path = (CORPUS / row["file"]).resolve()
            if not path.is_relative_to(CORPUS.resolve()):
                raise ValueError("Unsafe manifest path")
            raw = path.read_bytes()
            sources[row["file"]] = digest(raw)
            item = dict(id=row["id"], scenario=row["scenario"], group=row["group"],
                        attachment_type=row["attachment_type"], **extract(raw))
            item["text_sha256"] = digest(item["text"].encode())
            extraction.extend(dict(id=item["id"], **error) for error in item["extraction_errors"])
            output.write(json.dumps(item, ensure_ascii=False) + "\n")
    ids = [r["id"] for r in manifest]
    # Freeze identical full cohorts before any model inference, including every hard negative.
    write_json(results / "cohorts.json", dict(classification=ids, ner_qualitative=ids,
        smoke_ids=ids[:5], manifest_sha256=digest(manifest_raw), source_sha256=sources,
        prepared_sha256=digest(prepared.read_bytes()), protocol_sha256=digest((HERE / "protocol.json").read_bytes()),
        groups=dict(Counter(r["group"] for r in manifest)), selection="All 350, no outcome-dependent exclusions"))
    write_json(results / "extraction.json", dict(errors=extraction, messages=350,
        missing_ocr=sum("OCR unavailable" in e["error"] for e in extraction),
        note="Predictions on affected messages are end-to-end extraction-limited, not unambiguous model failures"))
    print(f"Frozen {len(ids)} inputs; {len(extraction)} extraction errors")


if __name__ == "__main__":
    main()