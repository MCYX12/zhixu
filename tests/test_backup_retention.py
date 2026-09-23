import json
from datetime import UTC, datetime, timedelta

from local_ai.backup import create_snapshot
from local_ai.backup_retention import prune_snapshots, retention_plan
from local_ai.config import Settings
from local_ai.workspace_store import WorkspaceStore


def test_daily_weekly_policy_never_deletes_manual_unmarked_corrupt_or_linked(tmp_path):
    root = tmp_path / "backups"
    root.mkdir()
    settings = Settings(tmp_path / "db", tmp_path)
    store = WorkspaceStore(settings.database)
    now = datetime(2026, 9, 22, 12, tzinfo=UTC)
    names = {}
    for age in range(36):
        created = now - timedelta(days=age)
        name = f"auto-{created:%Y%m%dT%H%M%SZ}-{age:08x}"
        names[age] = name
        create_snapshot(store, settings, root / name, origin="automatic")
        p = root / name / "manifest.json"
        manifest = json.loads(p.read_text())
        manifest["created_at"] = created.isoformat()
        p.write_text(json.dumps(manifest))
    # Pre-policy snapshots and manually created packages are not cleanup targets.
    for age, origin in [(31, "manual"), (32, None)]:
        p = root / names[age] / "manifest.json"
        m = json.loads(p.read_text())
        m["origin"] = origin
        p.write_text(json.dumps(m))
    (root / names[33] / "settings.json").write_text("corrupt")
    link = root / "auto-20200101T000000Z-ffffffff"
    link.symlink_to(root / names[31], target_is_directory=True)
    plan = retention_plan(root, names[0], now.timestamp())
    keep_ages = set(range(7)) | {7, 14, 21}
    assert not any(names[age] in plan["delete"] for age in keep_ages | {31, 32, 33})
    assert names[28] in plan["delete"]
    result = prune_snapshots(root, names[0], now.timestamp())
    assert result["deleted_count"] == len(plan["delete"])
    assert result["failed_count"] == 0
    assert all((root / names[age]).exists() for age in keep_ages | {31, 32, 33})
    assert link.is_symlink()


def test_no_valid_replacement_means_no_deletion(tmp_path):
    import pytest

    with pytest.raises(ValueError):
        prune_snapshots(tmp_path, "auto-20260922T000000Z-00000000", 1)
    assert list(tmp_path.iterdir()) == []
