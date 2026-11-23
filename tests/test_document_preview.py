import base64
import io
import json
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from PIL import Image

from app.document_preview import render
from app.preview_api import load


def test_preview_requires_original_permission_before_database_access():
    with pytest.raises(HTTPException) as error:
        load("secret", SimpleNamespace(originals=False), None)
    assert error.value.status_code == 403


def test_image_rasterization_and_limits():
    stream = io.BytesIO()
    Image.new("RGB", (30, 20), "white").save(stream, "TIFF")
    result = render(stream.getvalue(), '{}')
    assert result["pages"] == 1
    assert base64.b64decode(result["image"]).startswith(b"\x89PNG")
    with pytest.raises(ValueError):
        render(stream.getvalue(), '{"page":2}')
    with pytest.raises(ValueError):
        render(stream.getvalue(), '{"scale":10}')


def test_pdf_is_rasterized_not_returned_and_can_highlight():
    import fitz

    with fitz.open() as document:
        page = document.new_page()
        page.insert_text((40, 40), "confidential")
        data = document.tobytes()
    result = render(data, json.dumps({"highlights": ["confidential"]}))
    assert result["pages"] == 1
    assert base64.b64decode(result["image"]).startswith(b"\x89PNG")


def test_active_html_is_rejected():
    with pytest.raises(Exception):
        render(b'<html><script>alert(1)</script></html>', '{}')