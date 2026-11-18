"""Live Compose checks. Creates synthetic data only; preserves existing settings."""

import io
import json
import subprocess
import time
import uuid
from email.message import EmailMessage

import httpx
from PIL import Image, ImageDraw, ImageFont

from app.config import settings


def command(code):
    result = subprocess.run(
        ["docker", "compose", "exec", "-T", "worker", "python", "-c", code],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def main():
    run = uuid.uuid4().hex
    report = {"run": run}
    with httpx.Client(base_url="http://localhost:8080", timeout=180) as client:
        response = client.post(
            "/api/login", json={"username": "admin", "password": settings().admin_password}
        )
        response.raise_for_status()
        client.headers["X-CSRF-Token"] = response.json()["csrf"]
        text = "Confidential financial strategic budget revenue expenses internal forecast project " + run
        response = client.post("/api/references", files={"file": ("synthetic-reference.txt", text.encode())})
        response.raise_for_status()
        reference_id = response.json()["id"]
        report["reference_id"] = reference_id
        message = EmailMessage()
        message["From"] = "synthetic@example.test"
        message["To"] = "recipient@example.test"
        message["Subject"] = "Container integration " + run
        message.set_content(text + "\napi_key=synthetic_never_valid_secret")
        image = Image.new("RGB", (1400, 180), "white")
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 40)
        ImageDraw.Draw(image).text((20, 40), "CONFIDENTIAL FINANCIAL REPORT 2026", font=font, fill="black")
        stream = io.BytesIO()
        image.save(stream, format="PNG")
        message.add_attachment(stream.getvalue(), maintype="image", subtype="png", filename="scan.png")
        response = client.post("/api/import", files={"files": ("synthetic.eml", message.as_bytes())})
        response.raise_for_status()
        message_id = response.json()[0]["message_id"]
        for _ in range(90):
            row = client.get("/api/messages/" + message_id).json()
            if row["status"] in {"ANALYZED", "PARTIAL", "FAILED"}:
                break
            time.sleep(2)
        report["message_id"] = message_id
        report["status"] = row["status"]
        assert row["status"] == "ANALYZED", row
        assert "FINANCIAL REPORT" in row["text"]
        assert any(f["category"] == "REFERENCE_DOCUMENT" for f in row["analysis"]["findings"])
        report["ocr_and_reference"] = True
        response = client.get("/api/search", params={"q": run})
        response.raise_for_status()
        assert any(r["id"] == message_id for r in response.json()["items"])
        report["fts"] = True
        probe = json.loads(
            command("import json; from app.sandbox import call; print(json.dumps(call('probe',b'')))")
        )
        assert probe["network_denied"] and probe["database_secret"] is None
        report["sandbox"] = probe
        response = client.put(
            f"/api/retention/messages/{message_id}/hold",
            json={"enabled": True, "reason": "Synthetic integration legal hold"},
        )
        response.raise_for_status()
        assert response.json()["legal_hold"]
        response = client.post("/api/retention/cleanup", json={"dry_run": True})
        response.raise_for_status()
        assert message_id not in response.json()["candidates"]
        report["legal_hold_dry_run"] = True
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
