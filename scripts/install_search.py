"""Explicit network installation of the optional search service, isolated from the Gateway."""

import subprocess
from pathlib import Path

from start_search import REVISION

ROOT = Path(__file__).resolve().parent.parent


def main():
    source = ROOT / "data/searxng"
    if not source.exists():
        subprocess.run(
            [
                "git",
                "clone",
                "--no-checkout",
                "--filter=blob:none",
                "https://github.com/searxng/searxng.git",
                str(source),
            ],
            check=True,
        )
        subprocess.run(["git", "-C", str(source), "checkout", REVISION], check=True)
    actual = subprocess.check_output(
        ["git", "-C", str(source), "rev-parse", "HEAD"], text=True
    ).strip()
    if actual != REVISION:
        raise SystemExit(
            "Existing search checkout has a different revision; preserve it and review manually"
        )
    python = ROOT / "data/searxng-venv/bin/python"
    if not python.exists():
        subprocess.run(["uv", "venv", str(python.parent.parent), "--python", "3.13"], check=True)
    subprocess.run(
        [
            "uv",
            "pip",
            "install",
            "--python",
            str(python),
            "-r",
            str(ROOT / "config/search-requirements.lock"),
        ],
        check=True,
    )
    print("Installed search service. Start with python3 scripts/start_search.py")


if __name__ == "__main__":
    main()
