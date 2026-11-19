"""Read-only preview by default; explicit --apply is required to write DB.

Examples:
  python -m scripts.rulepacks preview config/rulepacks/base_ru.json
  python -m scripts.rulepacks apply config/rulepacks/base_ru.json --actor admin
  python -m scripts.rulepacks export --output /tmp/mailfire-rulepack.json
"""
import argparse
import json
from pathlib import Path

from app.db import transaction
from app.rulepacks import apply_pack, export_pack, inspect_pack, load_pack


def main():
    parser = argparse.ArgumentParser(description="Mail-Fire DLP rulepack import/export")
    commands = parser.add_subparsers(dest="command", required=True)
    for operation in ("preview", "apply"):
        cmd = commands.add_parser(operation)
        cmd.add_argument("file", type=Path)
        cmd.add_argument("--update-existing", action="store_true")
        if operation == "apply":
            cmd.add_argument("--actor", required=True, help="Audit actor identifier (admin/operator)")
    export = commands.add_parser("export")
    export.add_argument("--name", default="mailfire-export")
    export.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "export":
        with transaction() as session:
            output = export_pack(session, args.name).model_dump()
        target = args.output
        if target.exists():
            parser.error("Файл уже существует; выберите новый путь экспорта")
        target.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"Exported {len(output['categories'])} custom categories and {len(output['policies'])} policies to {target}")
        return
    pack = load_pack(args.file)
    with transaction() as session:
        if args.command == "preview":
            result = inspect_pack(session, pack, update_existing=args.update_existing)
        else:
            # All-or-nothing commit via transaction(); no automatic ingestion at startup.
            result = apply_pack(session, pack, actor=args.actor, update_existing=args.update_existing)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
