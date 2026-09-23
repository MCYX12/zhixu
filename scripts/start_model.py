import argparse
import json
import os
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument("--binary", default=os.environ.get("LLAMA_SERVER_BIN", "llama-server"))
args = parser.parse_args()
binary = shutil.which(args.binary)
if not binary:
    raise SystemExit("Set LLAMA_SERVER_BIN or pass --binary /path/to/llama-server")
lock = json.loads((ROOT / "config/model-lock.json").read_text())
model = ROOT / "models" / lock["filename"]
if not model.is_file() or model.stat().st_size != lock["size"]:
    raise SystemExit("Run python3 scripts/download_model.py first")
# 16K total with two slots is an initial candidate; inspect runtime per-slot context.
os.execv(
    binary,
    [
        binary,
        "--model",
        str(model),
        "--alias",
        "local-qwen",
        "--host",
        "127.0.0.1",
        "--port",
        "8080",
        "--ctx-size",
        "16384",
        "--parallel",
        "2",
        "--n-gpu-layers",
        "99",
        "--jinja",
        "--no-webui",
        "--metrics",
        "--cache-ram",
        "1024",
        "--ctx-checkpoints",
        "8",
    ],
)
