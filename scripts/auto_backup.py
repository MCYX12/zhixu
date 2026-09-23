"""launchd entry: check hourly and back up when the last success is 24h old."""

import argparse
import fcntl
import json
import os
import sys
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from local_ai.backup import create_snapshot, verify_snapshot  # noqa: E402
from local_ai.backup_retention import prune_snapshots  # noqa: E402
from local_ai.config import load_settings  # noqa: E402
from local_ai.store import Store  # noqa: E402


def run(root=ROOT, now=None, force=False):
    now = time.time() if now is None else now
    data = root / "data"
    data.mkdir(exist_ok=True)
    status = data / "auto-backup-status.json"
    with (data / "auto-backup.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return 0
        previous = {}
        try:
            previous = json.loads(status.read_text())
            if not isinstance(previous, dict):
                previous = {}
        except (OSError, ValueError):
            pass
        last = previous.get("last_success", 0)
        if not force and isinstance(last, (int, float)) and 0 <= now - last < 86400:
            name = previous.get("snapshot", "")
            if isinstance(name, str) and name and Path(name).name == name:
                try:
                    verify_snapshot(data / "backups" / name)
                    return 0
                except Exception:
                    pass
        result = {"last_attempt": now, "last_success": last, "state": "failed"}
        code = 1
        try:
            settings = load_settings()
            if not settings.database.is_file():
                raise ValueError("database_missing")
            backups = data / "backups"
            backups.mkdir(mode=0o700, exist_ok=True)
            destination = backups / (
                "auto-"
                + time.strftime("%Y%m%dT%H%M%SZ", time.gmtime(now))
                + "-"
                + uuid.uuid4().hex[:8]
            )
            create_snapshot(Store(settings.database), settings, destination, origin="automatic")
            verify_snapshot(destination)
            result.update(state="ok", last_success=now, snapshot=destination.name)
            code = 0
            try:
                result["cleanup"] = prune_snapshots(backups, destination.name, time.time())
            except Exception as error:
                result["cleanup"] = {"error": type(error).__name__}
        except Exception as error:
            # No database contents, credentials or source paths in persistent status.
            result["error"] = type(error).__name__
        temporary = data / (".backup-status-" + uuid.uuid4().hex)
        with os.fdopen(
            os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "w"
        ) as handle:
            json.dump(result, handle)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, status)
        print("自动备份完成" if code == 0 else "自动备份失败；下次检查将重试", flush=True)
        return code


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true", help="立即新建并校验备份，再执行保留策略")
    raise SystemExit(run(force=parser.parse_args().force))
