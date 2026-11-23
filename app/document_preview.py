"""Passive page rasterization; called only inside the parser sandbox. No OCR."""

import base64
import io
import json


def render(data, options):
    import pymupdf as fitz
    from PIL import Image

    options = json.loads(options)
    page_number = int(options.get("page", 1))
    scale = float(options.get("scale", 1))
    if not 1 <= page_number <= 1000 or not 0.5 <= scale <= 2:
        raise ValueError("Invalid page or scale")
    if data.startswith(b"%PDF-"):
        with fitz.open(stream=data, filetype="pdf") as document:
            if document.needs_pass or page_number > len(document):
                raise ValueError("Unavailable page")
            page = document[page_number - 1]
            if page.rect.width * page.rect.height * scale**2 > 16_000_000:
                raise ValueError("Page too large")
            for excerpt in options.get("highlights", [])[:30]:
                if isinstance(excerpt, str) and 2 <= len(excerpt) <= 200:
                    for rect in page.search_for(excerpt)[:50]:
                        page.add_highlight_annot(rect)
            image = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False).tobytes("png")
            pages = len(document)
    else:
        with Image.open(io.BytesIO(data)) as source:
            if source.format not in {"PNG", "JPEG", "WEBP", "TIFF", "GIF"}:
                raise ValueError("Unsupported image")
            pages = getattr(source, "n_frames", 1)
            if page_number > pages or source.width * source.height > 16_000_000:
                raise ValueError("Image too large")
            source.seek(page_number - 1)
            source.thumbnail((int(1600 * scale), int(1600 * scale)))
            output = io.BytesIO()
            source.convert("RGB").save(output, "PNG")
            image = output.getvalue()
    return {"image": base64.b64encode(image).decode(), "pages": pages}