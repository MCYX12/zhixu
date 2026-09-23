import json
import stat

import pytest

from local_ai.backup import create_snapshot, restore_snapshot, verify_snapshot
from local_ai.config import Settings
from local_ai.knowledge import ingest, search
from local_ai.store import User
from local_ai.workspace_store import WorkspaceStore


@pytest.fixture
def snapshot(tmp_path):
    knowledge = tmp_path / "knowledge"
    knowledge.mkdir()
    (knowledge / "private.md").write_text("Private PROJECT-TITAN detail")
    settings = Settings(tmp_path / "live.sqlite3", knowledge)
    store = WorkspaceStore(settings.database)
    key = store.create_user("alice", ["lab"])
    store.create_user("bob", ["lab"])
    ingest(store, settings, "alice", "private")
    token, _ = store.create_session(User("alice"))
    chat = store.save_conversation(
        User("alice"), "private", [{"role": "user", "content": "hello"}], "local"
    )
    directory = tmp_path / "snapshot"
    create_snapshot(store, settings, directory)
    return directory, store, settings, key, token, chat


def test_restore_keeps_identity_acl_and_conversation_but_clears_sessions(snapshot, tmp_path):
    directory, live, settings, key, token, chat = snapshot
    report = restore_snapshot(directory, tmp_path / "restored")
    restored = WorkspaceStore(tmp_path / "restored/state.sqlite3")
    assert restored.authenticate(key).id == "alice"
    assert restored.session(token) is None
    assert live.session(token) is not None
    assert search(restored, User("alice"), "PROJECT-TITAN")
    assert not search(restored, User("bob", ("lab",)), "PROJECT-TITAN")
    assert restored.conversation(User("alice"), chat["id"])
    assert restored.conversation(User("bob"), chat["id"]) is None
    assert report["live_database_replaced"] is False
    assert stat.S_IMODE((tmp_path / "restored").stat().st_mode) == 0o700
    assert stat.S_IMODE((tmp_path / "restored/state.sqlite3").stat().st_mode) == 0o600


@pytest.mark.parametrize("name", ["state.sqlite3", "settings.json", "model-lock.json"])
def test_tampering_prevents_restore(snapshot, tmp_path, name):
    directory, *_ = snapshot
    with (directory / name).open("ab") as f:
        f.write(b"changed")
    with pytest.raises(ValueError, match="校验失败"):
        restore_snapshot(directory, tmp_path / "restored")
    assert not (tmp_path / "restored").exists()


def test_never_overwrites_existing_destination(snapshot, tmp_path):
    directory, store, settings, *_ = snapshot
    before = (directory / "state.sqlite3").read_bytes()
    with pytest.raises(FileExistsError):
        create_snapshot(store, settings, directory)
    with pytest.raises(FileExistsError):
        restore_snapshot(directory, tmp_path)
    assert (directory / "state.sqlite3").read_bytes() == before


def test_symlink_rejected_and_backup_private_from_creation(snapshot, tmp_path):
    directory, store, *_ = snapshot
    link = tmp_path / "linked"
    link.symlink_to(directory, target_is_directory=True)
    with pytest.raises(ValueError):
        verify_snapshot(link)
    with pytest.raises(ValueError):
        store.backup(directory / "state.sqlite3")
    assert all(stat.S_IMODE(p.stat().st_mode) == 0o600 for p in directory.iterdir())


def test_manifest_not_a_dictionary_rejected(snapshot):
    directory, *_ = snapshot
    (directory / "manifest.json").write_text(json.dumps([]))
    with pytest.raises(ValueError):
        verify_snapshot(directory)
