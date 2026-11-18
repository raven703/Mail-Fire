"""Generate only synthetic EMLs in the explicitly selected user source folder."""

import argparse
from email.message import EmailMessage
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--count", type=int, default=10)
parser.add_argument("--directory", type=Path, default=Path("data/import/inbox"))
args = parser.parse_args()
args.directory.mkdir(parents=True, exist_ok=True)
for index in range(args.count):
    msg = EmailMessage()
    msg["From"] = "synthetic-sender@example.test"
    msg["To"] = "synthetic-recipient@example.test"
    msg["Subject"] = f"Синтетический пример {index}"
    msg["Message-ID"] = f"<synthetic-{index}@example.test>"
    msg.set_content("Коммерческая тайна\napi_key=synthetic_never_valid_token\nТолько тестовые данные.")
    path = args.directory / f"synthetic-{index:06}.eml"
    if not path.exists():
        temporary = path.with_suffix(".tmp")
        temporary.write_bytes(msg.as_bytes())
        temporary.rename(path)
