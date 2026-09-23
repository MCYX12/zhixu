"""Install/remove the current user's local backup LaunchAgent."""

import argparse
import os
import plistlib
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LABEL = "com.zhixu.workspace.backup"


def definition(root=ROOT):
    return {
        "Label": LABEL,
        "ProgramArguments": [str(root / ".venv/bin/python"), str(root / "scripts/auto_backup.py")],
        "WorkingDirectory": str(root),
        "RunAtLoad": True,
        "StartInterval": 3600,
        "ProcessType": "Background",
        "LowPriorityIO": True,
        "Umask": 0o077,
        "StandardOutPath": str(root / "data/auto-backup.log"),
        "StandardErrorPath": str(root / "data/auto-backup.log"),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["install", "status", "remove"])
    args = parser.parse_args()
    domain = f"gui/{os.getuid()}"
    path = Path.home() / "Library/LaunchAgents" / (LABEL + ".plist")
    if args.action == "status":
        return subprocess.run(["/bin/launchctl", "print", f"{domain}/{LABEL}"]).returncode
    if path.exists():
        old = plistlib.loads(path.read_bytes())
        if old.get("ProgramArguments") != definition()["ProgramArguments"]:
            raise SystemExit("同名任务属于其他安装路径，未修改")
        subprocess.run(["/bin/launchctl", "bootout", f"{domain}/{LABEL}"], capture_output=True)
    if args.action == "remove":
        path.unlink(missing_ok=True)
        print("已停用自动备份；已有备份保留")
        return 0
    path.parent.mkdir(parents=True, exist_ok=True)
    (ROOT / "data").mkdir(exist_ok=True)
    path.write_bytes(plistlib.dumps(definition()))
    path.chmod(0o600)
    subprocess.run(["/bin/launchctl", "enable", f"{domain}/{LABEL}"], check=True)
    subprocess.run(["/bin/launchctl", "bootstrap", domain, str(path)], check=True)
    print("已启用：登录后每小时检查，距上次成功备份满24小时则备份；失败下次重试。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
