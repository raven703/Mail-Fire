from scripts.migration_inventory import inventory


def test_inventory_captures_existing_contracts():
    result = inventory()
    assert {"model": "Message", "table": "messages"} in result["tables"]
    assert {"model": "Outbox", "table": "outbox"} in result["tables"]
    assert {
        "file": "app/api.py", "handler": "login", "method": "POST", "local_path": "/api/login"
    } in result["endpoints"]
    assert "frontend/src/main.tsx" in result["ui_components"]
    assert "frontend/src/style.css" in result["stylesheets"]
    assert "0007_unified_incidents.py" in result["alembic_migrations"]


def test_inventory_is_deterministic_and_has_no_duplicate_endpoints():
    result = inventory()
    assert result == inventory()
    keys = [(row["file"], row["method"], row["local_path"]) for row in result["endpoints"]]
    assert len(keys) == len(set(keys))