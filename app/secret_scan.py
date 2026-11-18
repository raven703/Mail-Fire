"""Gitleaks CLI adapter: bounded stdin, offline rules, no secret-bearing logs."""

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path


def scan(data):
    binary = shutil.which("gitleaks")
    if not binary:
        return {"status": "UNAVAILABLE", "findings": []}
    with tempfile.TemporaryDirectory(prefix="mailfire-gitleaks-") as directory:
        report = Path(directory) / "report.json"
        result = subprocess.run(
            [
                binary,
                "stdin",
                "--no-banner",
                "--log-level",
                "error",
                "--report-format",
                "json",
                "--report-path",
                str(report),
            ],
            input=data,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=30,
            cwd=directory,
            env={"PATH": os.path.dirname(binary), "HOME": directory, "GOMAXPROCS": "1"},
        )
        if result.returncode not in (0, 1):
            raise RuntimeError("Gitleaks scan failed")
        rows = json.loads(report.read_text()) if report.exists() else []
    from app.advanced_detectors import finding

    return {
        "status": "OK",
        "findings": [
            finding(
                "SECRET",
                "gitleaks",
                r.get("Match", ""),
                90,
                r.get("Description", "Gitleaks secret rule"),
                detector_rule=r["RuleID"],
            )
            for r in rows
        ],
    }
