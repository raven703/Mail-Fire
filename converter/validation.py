"""Bounded format validation before LibreOffice's permissive import detection."""
import io
import zipfile


def validate_document(data, ext):
    if ext in {"doc", "xls", "ppt"}:
        if not data.startswith(bytes.fromhex("d0cf11e0a1b11ae1")):
            raise ValueError("Expected OLE document")
        return
    required = {"docx": "word/document.xml", "xlsx": "xl/workbook.xml",
                "pptx": "ppt/presentation.xml"}[ext]
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        entries = archive.infolist()
        if len(entries) > 2000 or sum(e.file_size for e in entries) > 100 * 1024**2:
            raise ValueError("Expanded document limit")
        if any(e.flag_bits & 1 for e in entries):
            raise ValueError("Encrypted document")
        names = {e.filename for e in entries}
        if required not in names or "[Content_Types].xml" not in names:
            raise ValueError("Wrong Office format")