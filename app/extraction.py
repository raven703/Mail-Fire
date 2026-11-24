import io
import zipfile
from pathlib import PurePosixPath

from bs4 import BeautifulSoup

from app.config import settings


def extract(data, name, depth=0, budget=None, *, use_ocr=True):
    budget = budget if budget is not None else [0, 0]
    budget[0] += 1
    budget[1] += len(data)
    if budget[0] > settings().max_objects or budget[1] > settings().max_expanded_bytes:
        raise ValueError("Лимит извлечения")
    suffix = PurePosixPath(name.lower()).suffix
    try:
        if data.startswith(b"%PDF"):
            import pymupdf

            with pymupdf.open(stream=data, filetype="pdf") as doc:
                if doc.needs_pass:
                    return "", "ENCRYPTED", {}
                if len(doc) > 200:
                    return "", "PARTIAL", {"error": "page limit"}
                pages = []
                ocr_pages = []
                for index, page in enumerate(doc):
                    text = page.get_text()
                    if len(text.strip()) < 20 and use_ocr and settings().ocr_backend != "disabled":
                        from app.ocr import recognize

                        text, metadata = recognize(
                            page.get_pixmap(matrix=pymupdf.Matrix(2, 2)).tobytes("png"), index + 1
                        )
                        ocr_pages.append(metadata)
                    pages.append(text)
                return (
                    "\n".join(pages),
                    "PARTIAL" if any(len(t.strip()) < 20 for t in pages) else "ANALYZED",
                    {
                        "ocr_required": any(len(t.strip()) < 20 for t in pages),
                        "pages": len(pages),
                        "ocr": ocr_pages,
                    },
                )
        if suffix in {".png", ".jpg", ".jpeg", ".tiff", ".tif", ".bmp", ".webp"}:
            if not use_ocr or settings().ocr_backend == "disabled":
                return "", "PARTIAL", {"ocr_required": True}
            from app.ocr import recognize

            text, details = recognize(data)
            return text, "ANALYZED" if text.strip() else "PARTIAL", details
        if suffix == ".docx":
            from docx import Document

            doc = Document(io.BytesIO(data))
            return (
                "\n".join(
                    [p.text for p in doc.paragraphs]
                    + [" ".join(c.text for c in r.cells) for t in doc.tables for r in t.rows]
                ),
                "ANALYZED",
                {},
            )
        if suffix == ".xlsx":
            from openpyxl import load_workbook

            book = load_workbook(io.BytesIO(data), read_only=True, data_only=False)
            try:
                return (
                    "\n".join(
                        " ".join(str(c) for c in row if c is not None)
                        for sheet in book
                        for row in sheet.values
                    ),
                    "ANALYZED",
                    {},
                )
            finally:
                book.close()
        if suffix == ".pptx":
            from pptx import Presentation

            return (
                "\n".join(
                    s.text
                    for slide in Presentation(io.BytesIO(data)).slides
                    for s in slide.shapes
                    if s.has_text_frame
                ),
                "ANALYZED",
                {},
            )
        if zipfile.is_zipfile(io.BytesIO(data)):
            if depth >= settings().max_archive_depth:
                return "", "PARTIAL", {"error": "archive depth"}
            texts, states, findings = [], [], []
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                for member in archive.infolist():
                    path = PurePosixPath(member.filename)
                    if (
                        path.is_absolute()
                        or ".." in path.parts
                        or member.external_attr >> 16 & 0o170000 == 0o120000
                    ):
                        raise ValueError("Unsafe archive path")
                    if member.is_dir():
                        continue
                    if member.flag_bits & 1:
                        states.append("ENCRYPTED")
                        continue
                    if (
                        member.file_size > settings().max_expanded_bytes - budget[1]
                        or member.file_size > max(member.compress_size, 1) * 200
                    ):
                        raise ValueError("Archive expansion limit")
                    if budget[0] >= settings().max_objects:
                        raise ValueError("Archive object limit")
                    child = archive.read(member)
                    from app.advanced_detectors import static_scan

                    findings.extend(static_scan(child, member.filename)["findings"])
                    child_text, state, child_details = extract(
                        child, member.filename, depth + 1, budget, use_ocr=use_ocr
                    )
                    findings.extend(child_details.get("findings", []))
                    texts.append(child_text)
                    states.append(state)
            return (
                "\n".join(texts),
                "ANALYZED" if all(s == "ANALYZED" for s in states) else "PARTIAL",
                {
                    "children": states,
                    "findings": findings,
                    **({"ocr_required": any(s == "PARTIAL" for s in states)} if not use_ocr else {}),
                },
            )
        if suffix in {
            ".txt",
            ".csv",
            ".json",
            ".xml",
            ".html",
            ".htm",
            ".py",
            ".js",
            ".ts",
            ".sql",
            ".ps1",
            ".sh",
            ".c",
            ".cpp",
            ".h",
            ".java",
            ".go",
            ".cs",
        }:
            text = data.decode("utf-8", errors="replace")
            if suffix in {".html", ".htm"}:
                text = BeautifulSoup(text, "html.parser").get_text(" ")
            return text, "ANALYZED", {}
        return "", "UNSUPPORTED", {"reason": "Parser not installed or format unsupported"}
    except Exception as exc:
        return "", "FAILED", {"error": type(exc).__name__}
