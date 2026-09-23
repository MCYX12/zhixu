"""Conservative retention for verified, explicitly tagged automatic snapshots."""

import re
import shutil
from datetime import UTC, datetime
from pathlib import Path

from .backup import verify_snapshot

NAME = re.compile(r"auto-\d{8}T\d{6}Z-[0-9a-f]{8}")


def retention_plan(directory, protected, now):
    directory = Path(directory)
    if directory.is_symlink() or not directory.is_dir():
        raise ValueError("Invalid backup root")
    entries, skipped = [], []
    today = datetime.fromtimestamp(now, UTC).date()
    for path in directory.iterdir():
        if not NAME.fullmatch(path.name) or path.is_symlink() or not path.is_dir():
            continue
        try:
            manifest = verify_snapshot(path)
            if manifest.get("origin") != "automatic":
                continue
            created = datetime.fromisoformat(manifest["created_at"])
            if created.tzinfo is None or created.timestamp() > now:
                raise ValueError("Invalid snapshot date")
            entries.append(
                (created.timestamp(), path.name, (today - created.astimezone(UTC).date()).days)
            )
        except Exception:
            skipped.append(path.name)
    entries.sort(reverse=True)
    keep = {protected}
    if entries:
        keep.add(entries[0][1])
    days, weeks = set(), set()
    for _, name, age in entries:
        if age < 7 and age not in days:
            days.add(age)
            keep.add(name)
        if age < 28 and age // 7 not in weeks:
            weeks.add(age // 7)
            keep.add(name)
    return {
        "delete": [name for _, name, _ in entries if name not in keep],
        "keep": sorted(keep),
        "skipped": skipped,
    }


def prune_snapshots(directory, protected, now):
    directory = Path(directory)
    if not NAME.fullmatch(protected):
        raise ValueError("Invalid protected snapshot")
    # No cleanup unless the replacement backup exists and passes full verification.
    replacement = verify_snapshot(directory / protected)
    if replacement.get("origin") != "automatic":
        raise ValueError("Replacement is not an automatic snapshot")
    plan = retention_plan(directory, protected, now)
    deleted, failures = [], []
    for name in plan["delete"]:
        try:
            path = directory / name
            if verify_snapshot(path).get("origin") != "automatic":
                raise ValueError("Snapshot changed")
            shutil.rmtree(path)
            deleted.append(name)
        except Exception:
            failures.append(name)
    return {
        "deleted_count": len(deleted),
        "skipped_count": len(plan["skipped"]),
        "failed_count": len(failures),
    }
