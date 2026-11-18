import os

import pytest

pytestmark = pytest.mark.skipif(not os.getenv("MAILFIRE_TEST_DB"), reason="Requires PostgreSQL")


def test_folder_stability_idempotency_and_archive_exclusion(tmp_path, monkeypatch):
    from sqlalchemy import func, select
    from test_core import synthetic_mail

    from app.config import settings
    from app.db import transaction
    from app.importer import scan
    from app.models import ImportRecord

    monkeypatch.setattr(settings(), "import_stability_seconds", 0)
    path = tmp_path / "folder-synthetic.eml"
    path.write_bytes(synthetic_mail())
    (tmp_path / "symlink.eml").symlink_to(path)
    archive = tmp_path / ".imported"
    archive.mkdir()
    (archive / "ignored.eml").write_bytes(synthetic_mail())
    observed = {}
    scan(tmp_path, observed)
    assert str(path) in observed
    scan(tmp_path, observed)
    scan(tmp_path, observed)
    with transaction() as db:
        assert (
            db.scalar(select(func.count()).select_from(ImportRecord).where(ImportRecord.name == path.name))
            >= 1
        )
        assert not db.scalar(select(ImportRecord).where(ImportRecord.name == "symlink.eml"))
        assert not db.scalar(select(ImportRecord).where(ImportRecord.name == ".imported/ignored.eml"))
