"""Download the exact official core artifact and verify it before extraction."""
import gzip
import hashlib
import io
import json
import os
import sys
import urllib.request
from pathlib import Path

manifest = json.loads(Path("upstream.json").read_text())
asset = manifest["assets"][sys.argv[1]]
request = urllib.request.Request(asset["url"], headers={"User-Agent": "chatgpt3api-mihomo-build"})
with urllib.request.urlopen(request, timeout=90) as response:
    archive = response.read(40 * 1024 * 1024 + 1)
if len(archive) > 40 * 1024 * 1024 or hashlib.sha256(archive).hexdigest() != asset["sha256"]:
    raise SystemExit("Official Mihomo artifact checksum mismatch")
with gzip.GzipFile(fileobj=io.BytesIO(archive)) as compressed:
    binary = compressed.read(100 * 1024 * 1024 + 1)
if len(binary) > 100 * 1024 * 1024:
    raise SystemExit("Mihomo artifact exceeds extraction limit")
Path("/out").mkdir(exist_ok=True)
Path("/out/mihomo").write_bytes(binary)
os.chmod("/out/mihomo", 0o755)
