import io
import zipfile

import pytest

from converter.validation import validate_document


@pytest.mark.parametrize("ext,member", [("docx", "word/document.xml"),
                                      ("xlsx", "xl/workbook.xml"),
                                      ("pptx", "ppt/presentation.xml")])
def test_office_container_validation(ext, member):
    data = io.BytesIO()
    with zipfile.ZipFile(data, "w") as archive:
        archive.writestr('[Content_Types].xml', '<Types/>')
        archive.writestr(member, '<document/>')
    validate_document(data.getvalue(), ext)
    with pytest.raises(Exception):
        validate_document(b'plain text pretending to be Office', ext)


def test_wrong_office_format_and_legacy_signature():
    data = io.BytesIO()
    with zipfile.ZipFile(data, "w") as archive:
        archive.writestr('[Content_Types].xml', '<Types/>')
    with pytest.raises(ValueError):
        validate_document(data.getvalue(), 'docx')
    with pytest.raises(ValueError):
        validate_document(b'<script>unsafe</script>', 'doc')