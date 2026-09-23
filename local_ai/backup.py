"""Local snapshot bundles and restore rehearsals; never replace a live database."""

import hashlib
import json
import os
import shutil
import sqlite3
import time
import tomllib
from contextlib import closing
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

from .config import ROOT

FILES = {"state.sqlite3", "settings.json", "model-lock.json"}
TABLES = (
    "users",
    "api_keys",
    "documents",
    "chunks",
    "document_files",
    "conversations",
    "web_sessions",
    "web_sources",
    "audit_events",
)


def automatic_backup_status():
    """Expose only operational timestamps, never backup contents or paths."""
    try:
        state = json.loads((ROOT / "data/auto-backup-status.json").read_text())
        last = state.get("last_success", 0)
        attempt = state.get("last_attempt", 0)
        if type(last) not in (int, float) or type(attempt) not in (int, float):
            raise ValueError("invalid status")
        return {
            "retention": "7天每日一份 + 近4周每周一份",
            "cleanup_warning": bool(
                state.get("cleanup", {}).get("error")
                or state.get("cleanup", {}).get("failed_count")
            ),
            "deleted_count": state.get("cleanup", {}).get("deleted_count", 0),
            "state": "failed"
            if state.get("state") != "ok"
            else "stale"
            if time.time() - last > 90000
            else "ok",
            "last_success": last,
            "last_attempt": attempt,
        }
    except (OSError, ValueError, AttributeError):
        return {"state": "unknown", "last_success": 0, "last_attempt": 0}


def digest(path):
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def write_json(path, value):
    with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "w") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2, default=str)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())


def database_report(path):
    with closing(sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)) as db:
        if db.execute("PRAGMA integrity_check").fetchall() != [("ok",)]:
            raise ValueError("数据库完整性检查失败")
        if db.execute("PRAGMA foreign_key_check").fetchone() is not None:
            raise ValueError("数据库外键检查失败")
        names = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if not {"users", "api_keys", "documents", "chunks"} <= names:
            raise ValueError("不是知序数据库")
        return {
            name: db.execute(f'SELECT COUNT(*) FROM "{name}"').fetchone()[0]
            for name in TABLES
            if name in names
        }


def create_snapshot(store, settings, destination, origin="manual"):
    destination = Path(destination)
    destination.mkdir(mode=0o700, parents=False, exist_ok=False)
    try:
        database = destination / "state.sqlite3"
        store.backup(database)
        # Standalone backup must not require a live WAL sidecar.
        with closing(sqlite3.connect(database)) as db:
            db.execute("PRAGMA journal_mode=DELETE")
        counts = database_report(database)
        write_json(destination / "settings.json", asdict(settings))
        write_json(
            destination / "model-lock.json",
            json.loads((ROOT / "config/model-lock.json").read_text()),
        )
        manifest = {
            "origin": origin,
            "format": "zhixu-backup-v1",
            "created_at": datetime.now(UTC).isoformat(),
            "app_version": tomllib.loads((ROOT / "pyproject.toml").read_text())["project"][
                "version"
            ],
            "files": {
                name: {
                    "sha256": digest(destination / name),
                    "size": (destination / name).stat().st_size,
                }
                for name in sorted(FILES)
            },
            "counts": counts,
        }
        write_json(destination / "manifest.json", manifest)
        verify_snapshot(destination)
        return manifest
    except BaseException:
        # Only this newly-created directory is removed; existing destinations are refused.
        shutil.rmtree(destination)
        raise


def verify_snapshot(directory):
    directory = Path(directory)
    if directory.is_symlink() or not directory.is_dir():
        raise ValueError("备份目录无效")
    for name in FILES | {"manifest.json"}:
        p = directory / name
        if p.is_symlink() or not p.is_file():
            raise ValueError("备份文件缺失或为符号链接")
    if {p.name for p in directory.iterdir()} != FILES | {"manifest.json"}:
        raise ValueError("备份目录包含额外文件，拒绝恢复")
    if (directory / "manifest.json").stat().st_size > 65536:
        raise ValueError("备份清单过大")
    manifest = json.loads((directory / "manifest.json").read_text())
    if (
        not isinstance(manifest, dict)
        or manifest.get("format") != "zhixu-backup-v1"
        or not isinstance(manifest.get("files"), dict)
        or set(manifest["files"]) != FILES
        or not isinstance(manifest.get("created_at"), str)
    ):
        raise ValueError("不支持的备份格式")
    for name, expected in manifest["files"].items():
        if (
            not isinstance(expected, dict)
            or type(expected.get("size")) is not int
            or not isinstance(expected.get("sha256"), str)
        ):
            raise ValueError("备份清单字段无效")
        p = directory / name
        if p.stat().st_size != expected["size"] or digest(p) != expected["sha256"]:
            raise ValueError(f"备份文件校验失败：{name}")
    counts = database_report(directory / "state.sqlite3")
    if counts != manifest.get("counts"):
        raise ValueError("数据库记录数量与清单不一致")
    return manifest


def restore_snapshot(source, destination):
    source, destination = Path(source), Path(destination)
    manifest = verify_snapshot(source)
    destination.mkdir(mode=0o700, parents=False, exist_ok=False)
    try:
        database = destination / "state.sqlite3"
        with (source / "state.sqlite3").open("rb") as src:
            with os.fdopen(
                os.open(database, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "wb"
            ) as dst:
                shutil.copyfileobj(src, dst)
                dst.flush()
                os.fsync(dst.fileno())
        if digest(database) != manifest["files"]["state.sqlite3"]["sha256"]:
            raise ValueError("恢复期间源文件发生变化")
        with closing(sqlite3.connect(database)) as db:
            if "web_sessions" in manifest["counts"]:
                db.execute("DELETE FROM web_sessions")
                db.commit()
        report = {
            "source_created_at": manifest["created_at"],
            "counts": database_report(database),
            "web_sessions_cleared": True,
            "live_database_replaced": False,
        }
        write_json(destination / "restore-report.json", report)
        return report
    except BaseException:
        shutil.rmtree(destination)
        raise
