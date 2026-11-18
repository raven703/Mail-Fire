import io
import zipfile

import pytest

from app.uploads import upload_members


def archive(name, value):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr(name, value)
    return stream.getvalue()


def test_zip_mail():
    from test_core import synthetic_mail

    data = synthetic_mail()
    assert upload_members(archive("nested/message.eml", data), "test.zip") == [("nested/message.eml", data)]


@pytest.mark.parametrize(
    "name", ["../escape.eml", "/absolute.eml", "C:\\mail.eml", "script.py", "nested.zip"]
)
def test_unsafe_zip(name):
    with pytest.raises(ValueError):
        upload_members(archive(name, b"test"), "test.zip")


def test_zip_bomb():
    with pytest.raises(ValueError):
        upload_members(archive("bomb.eml", b"a" * 1000000), "test.zip")
