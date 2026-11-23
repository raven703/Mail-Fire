"""Single-slot, secret-free Office conversion broker on an internal network."""
import os
import subprocess
import tempfile
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
from validation import validate_document


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200 if self.path == "/health" else 404)
        self.end_headers()

    def do_POST(self):
        url = urlsplit(self.path)
        ext = parse_qs(url.query).get("ext", [""])[0]
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if url.path != "/convert" or ext not in {"doc", "docx", "xls", "xlsx", "ppt", "pptx"}:
                raise ValueError("Unsupported format")
            if not 0 < size <= 20 * 1024**2:
                raise ValueError("Size limit")
            self.connection.settimeout(75)
            data = self.rfile.read(size)
            if len(data) != size:
                raise ValueError("Truncated request")
            validate_document(data, ext)
            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                profile = root / "profile" / "user"
                profile.mkdir(parents=True)
                # Disable macros and updating document links, including embedded documents.
                (profile / "registrymodifications.xcu").write_text('''<?xml version="1.0"?>
<oor:items xmlns:oor="http://openoffice.org/2001/registry">
<item oor:path="/org.openoffice.Office.Common/Security/Scripting"><prop oor:name="MacroSecurityLevel" oor:op="fuse"><value>3</value></prop><prop oor:name="DisableMacrosExecution" oor:op="fuse"><value>true</value></prop></item>
<item oor:path="/org.openoffice.Office.Writer/Content/Update"><prop oor:name="Link" oor:op="fuse"><value>2</value></prop></item>
</oor:items>''')
                source = root / ("document." + ext)
                source.write_bytes(data)
                subprocess.run(["libreoffice", "-env:UserInstallation=" + (root / "profile").as_uri(),
                                "--headless", "--nologo", "--nodefault", "--norestore", "--convert-to",
                                "pdf", "--outdir", directory, str(source)],
                               check=True, timeout=60, stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL, env={"HOME": directory, "PATH": os.defpath})
                result = root / "document.pdf"
                if result.stat().st_size > 20 * 1024**2:
                    raise ValueError("Output limit")
                data = result.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "application/pdf")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
        except Exception:
            self.send_error(422, "Conversion unavailable")

    def log_message(self, *args):
        pass


HTTPServer(("0.0.0.0", 8091), Handler).serve_forever()