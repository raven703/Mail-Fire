"""CLI for versioned DLP rulepack management.

Examples on running API container (files streamed over stdin/stdout):
  docker compose exec -T api python -m app.rulepacks_cli preview - < config/rulepacks/base_ru.json
  docker compose exec -T api python -m app.rulepacks_cli apply - --actor admin < config/rulepacks/base_ru.json
  docker compose exec -T api python -m app.rulepacks_cli export --output - > exported-rules.json
"""
import argparse
import json
import sys
from pathlib import Path

from app.db import transaction
from app.models import Audit
from app.rulepacks import apply_pack, export_pack, inspect_pack, load_pack


def main():
    parser = argparse.ArgumentParser(description="Mail-Fire DLP rulepack preview/import/export")
    commands = parser.add_subparsers(dest="command", required=True)
    for operation in ("preview", "apply"):
        command = commands.add_parser(operation)
        command.add_argument("file", help="Path to a JSON rulepack or '-' for stdin")
        command.add_argument("--update-existing", action="store_true")
        if operation == "apply":
            command.add_argument("--actor", required=True, help="Audit actor identifier")
    export = commands.add_parser("export")
    export.add_argument("--name", default="mailfire-export")
    export.add_argument("--output", required=True, help="Destination file or '-' for stdout")
    args = parser.parse_args()
    if args.command == "export":
        with transaction() as session:
            output = export_pack(session, args.name).model_dump()
            session.add(Audit(actor="rulepacks-cli", action="rulepack_export", target=args.name))
        payload = json.dumps(output, ensure_ascii=False, indent=2) + "\n"
        if args.output == "-":
            sys.stdout.write(payload)
        else:
            target = Path(args.output)
            if target.exists():
                parser.error("Файл уже существует; выберите новый путь экспорта")
            target.write_text(payload, encoding="utf-8")
            print(f"Exported {len(output['categories'])} categories and {len(output['policies'])} policies to {target}")
        return
    pack = load_pack(args.file)
    with transaction() as session:
        if args.command == "preview":
            result = inspect_pack(session, pack, update_existing=args.update_existing)
        else:
            result = apply_pack(session, pack, actor=args.actor, update_existing=args.update_existing)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
