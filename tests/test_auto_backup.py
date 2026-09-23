import json
from pathlib import Path

from local_ai.config import Settings
from local_ai.workspace_store import WorkspaceStore
from scripts import auto_backup
from scripts.manage_auto_backup import definition


def test_daily_due_and_deleted_backup_recreated(tmp_path, monkeypatch):
    settings = Settings(tmp_path / "state.sqlite3", tmp_path)
    WorkspaceStore(settings.database)
    monkeypatch.setattr(auto_backup, "load_settings", lambda: settings)
    assert auto_backup.run(tmp_path, now=100000) == 0
    status = tmp_path / "data/auto-backup-status.json"
    first = json.loads(status.read_text())
    assert auto_backup.run(tmp_path, now=100500) == 0
    assert json.loads(status.read_text()) == first
    assert auto_backup.run(tmp_path, now=186400) == 0
    assert json.loads(status.read_text())["last_success"] == 186400
    newest = json.loads(status.read_text())["snapshot"]
    (tmp_path / "data/backups" / newest / "manifest.json").unlink()
    assert auto_backup.run(tmp_path, now=186500) == 0
    assert json.loads(status.read_text())["snapshot"] != newest


def test_failure_record_and_retry_without_claiming_success(tmp_path, monkeypatch):
    settings = Settings(tmp_path / "missing.sqlite3", tmp_path)
    monkeypatch.setattr(auto_backup, "load_settings", lambda: settings)
    assert auto_backup.run(tmp_path, now=100000) == 1
    status = tmp_path / "data/auto-backup-status.json"
    assert json.loads(status.read_text())["last_success"] == 0
    WorkspaceStore(settings.database)
    assert auto_backup.run(tmp_path, now=100001) == 0
    assert json.loads(status.read_text())["state"] == "ok"


def test_launch_agent_preserves_space_paths_and_has_no_shell():
    root = Path("/tmp/space project")
    config = definition(root)
    assert config["ProgramArguments"] == [
        str(root / ".venv/bin/python"),
        str(root / "scripts/auto_backup.py"),
    ]
    assert config["RunAtLoad"] and config["StartInterval"] == 3600
    assert "KeepAlive" not in config
