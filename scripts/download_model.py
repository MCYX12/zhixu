"""Explicit installation step; never invoked by a chat request."""

import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
lock = json.loads((ROOT / "config/model-lock.json").read_text())
directory = ROOT / "models"
directory.mkdir(exist_ok=True)
target = directory / lock["filename"]
partial = target.with_suffix(".gguf.part")
if not target.exists():
    url = (
        f"https://huggingface.co/{lock['repository']}/resolve/{lock['revision']}/{lock['filename']}"
    )
    subprocess.run(
        [
            "curl",
            "--fail",
            "--location",
            "--retry",
            "3",
            "--connect-timeout",
            "20",
            "--continue-at",
            "-",
            "--output",
            str(partial),
            url,
        ],
        check=True,
    )
    check = partial
else:
    check = target
with check.open("rb") as f:
    digest = hashlib.file_digest(f, "sha256").hexdigest()
if check.stat().st_size != lock["size"] or digest != lock["sha256"]:
    raise SystemExit("Model checksum mismatch; file was not activated")
if check == partial:
    partial.replace(target)
print(f"Verified: {target}")
