"""Read-only, dependency-free inventory for the Django migration parity gate."""

import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def inventory(root=ROOT):
    endpoints = []
    tables = []
    for path in sorted((root / "app").glob("*.py")):
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for decorator in node.decorator_list:
                    if not isinstance(decorator, ast.Call):
                        continue
                    target = decorator.func
                    if not isinstance(target, ast.Attribute) or target.attr not in {
                        "get", "post", "put", "patch", "delete", "head", "options"
                    }:
                        continue
                    if not isinstance(target.value, ast.Name) or target.value.id not in {"app", "router"}:
                        continue
                    if decorator.args and isinstance(decorator.args[0], ast.Constant):
                        endpoints.append({
                            "file": path.relative_to(root).as_posix(),
                            "handler": node.name,
                            "method": target.attr.upper(),
                            "local_path": decorator.args[0].value,
                        })
            if isinstance(node, ast.ClassDef):
                for statement in node.body:
                    if isinstance(statement, ast.Assign) and any(
                        isinstance(target, ast.Name) and target.id == "__tablename__"
                        for target in statement.targets
                    ):
                        tables.append({"model": node.name, "table": ast.literal_eval(statement.value)})
    return {
        "note": "Paths are decorator-local; router prefixes must be resolved during porting.",
        "endpoints": endpoints,
        "tables": tables,
        "ui_components": sorted(p.relative_to(root).as_posix() for p in (root / "frontend/src").glob("*.tsx")),
        "stylesheets": sorted(p.relative_to(root).as_posix() for p in (root / "frontend/src").glob("*.css")),
        "tests": sorted(p.relative_to(root).as_posix() for p in (root / "tests").glob("test_*.py")),
        "alembic_migrations": sorted(p.name for p in (root / "migrations/versions").glob("*.py")),
    }


if __name__ == "__main__":
    print(json.dumps(inventory(), ensure_ascii=False, indent=2))