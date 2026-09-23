import os
import stat

import pytest

from local_ai.store import User
from local_ai.workspace_store import WorkspaceStore


def test_rotation_revokes_all_old_keys_and_sessions(tmp_path):
    store = WorkspaceStore(tmp_path / "db")
    old = store.create_user("alice", ["lab"])
    token, _ = store.create_session(User("alice"))
    target = tmp_path / "replacement.key"
    store.rotate_key("alice", target)
    assert store.authenticate(old) is None
    assert store.session(token) is None
    assert store.authenticate(target.read_text().strip()).groups == ("lab",)
    assert stat.S_IMODE(target.stat().st_mode) == 0o600


def test_existing_key_file_never_overwritten(tmp_path):
    store = WorkspaceStore(tmp_path / "db")
    old = store.create_user("alice", [])
    target = tmp_path / "existing.key"
    target.write_text("preserve")
    with pytest.raises(FileExistsError):
        store.rotate_key("alice", target)
    assert target.read_text() == "preserve" and store.authenticate(old)


def test_failed_file_sync_keeps_original_credentials(tmp_path, monkeypatch):
    store = WorkspaceStore(tmp_path / "db")
    old = store.create_user("alice", [])
    target = tmp_path / "replacement.key"
    monkeypatch.setattr(os, "fsync", lambda fd: (_ for _ in ()).throw(OSError("disk failed")))
    with pytest.raises(OSError):
        store.rotate_key("alice", target)
    assert store.authenticate(old) and not target.exists()


def test_disabled_user_cannot_rotate(tmp_path):
    store = WorkspaceStore(tmp_path / "db")
    store.create_user("alice", [])
    store.disable_user("alice")
    with pytest.raises(ValueError):
        store.rotate_key("alice", tmp_path / "replacement.key")
    assert not (tmp_path / "replacement.key").exists()
