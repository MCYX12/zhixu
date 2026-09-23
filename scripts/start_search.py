"""Run the separately installed, pinned SearXNG on loopback only."""

import os
import secrets
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REVISION = "42829cecd6438e9b8bd46b4f402444d90c822e37"


def main():
    source = ROOT / "data/searxng"
    python = ROOT / "data/searxng-venv/bin/python"
    if not python.exists() or not source.exists():
        raise SystemExit("Run python3 scripts/install_search.py first")
    revision = subprocess.check_output(
        ["git", "-C", str(source), "rev-parse", "HEAD"], text=True
    ).strip()
    if revision != REVISION:
        raise SystemExit("SearXNG revision differs from the tested version")
    cache = ROOT / "data/searxng-cache"
    cache.mkdir(exist_ok=True)
    env = {
        k: v
        for k, v in os.environ.items()
        if k.lower() not in {"http_proxy", "https_proxy", "all_proxy", "no_proxy"}
    }
    env.update(
        {
            "SEARXNG_SETTINGS_PATH": str(ROOT / "config/searxng.yml"),
            "SEARXNG_SECRET": secrets.token_hex(32),
            "TMPDIR": str(cache),
            "PYTHONPATH": os.pathsep.join((str(ROOT), str(source))),
        }
    )
    os.chdir(source)
    os.execve(
        python,
        [str(python), str(ROOT / "scripts/search_runtime.py")],
        env,
    )


if __name__ == "__main__":
    main()
