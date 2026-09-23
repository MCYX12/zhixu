import argparse
import json
import re
import sqlite3
import sys
import time
from pathlib import Path

import uvicorn

from .config import load_settings
from .knowledge import ingest
from .store import Store


def identifier(value: str):
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", value):
        raise argparse.ArgumentTypeError("Use 1–64 letters, digits, underscore or hyphen")
    return value


def main():
    parser = argparse.ArgumentParser(description="Local-first AI administration")
    parser.add_argument("--config")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("serve")
    cloud_check = sub.add_parser("cloud-check", help="离线检查云端接入配置，不发送请求")
    cloud_check.add_argument("profile", type=Path)
    create = sub.add_parser("create-user")
    create.add_argument("user", type=identifier)
    create.add_argument("--group", action="append", default=[], type=identifier)
    create.add_argument("--role", choices=["admin", "member"], default="member")
    create.add_argument("--key-file", type=Path, required=True)
    rotate = sub.add_parser("rotate-key", help="轮换账号密钥，撤销旧密钥和网页登录会话")
    rotate.add_argument("user", type=identifier)
    rotate.add_argument("--key-file", type=Path, required=True)
    disable = sub.add_parser("disable-user")
    disable.add_argument("user", type=identifier)
    role = sub.add_parser("set-role")
    role.add_argument("user", type=identifier)
    role.add_argument("role", choices=["admin", "member"])
    scan = sub.add_parser("ingest")
    scan.add_argument("--owner", required=True, type=identifier)
    scan.add_argument("--visibility", choices=["private", "group", "public"], default="private")
    scan.add_argument("--workspace", type=identifier)
    scan.add_argument("--watch-seconds", type=int, default=0)
    delete = sub.add_parser("delete-document")
    delete.add_argument("document_id")
    backup = sub.add_parser("backup")
    backup.add_argument("destination", type=Path)
    snapshot = sub.add_parser("snapshot", help="创建含校验清单的本机备份目录")
    snapshot.add_argument("destination", type=Path)
    verify = sub.add_parser("verify-backup", help="校验备份而不修改当前数据库")
    verify.add_argument("source", type=Path)
    restore = sub.add_parser("restore-backup", help="恢复到全新目录，绝不覆盖在线数据库")
    restore.add_argument("source", type=Path)
    restore.add_argument("destination", type=Path)
    args = parser.parse_args()
    if args.command == "cloud-check":
        from .cloud_setup import inspect_profile

        result = inspect_profile(args.profile)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        sys.exit(0 if result["configured"] else 1)
    if args.command in {"verify-backup", "restore-backup"}:
        from .backup import restore_snapshot, verify_snapshot

        try:
            result = (
                verify_snapshot(args.source)
                if args.command == "verify-backup"
                else restore_snapshot(args.source, args.destination)
            )
        except (OSError, ValueError, sqlite3.Error) as error:
            parser.exit(1, f"备份操作未完成：{error}\n")
        print(json.dumps(result, ensure_ascii=False))
        return
    settings = load_settings(args.config)
    store = Store(settings.database)
    if args.command == "serve":
        from .api import create_app

        uvicorn.run(
            create_app(settings),
            host=settings.host,
            port=settings.port,
            workers=1,
            access_log=False,
            proxy_headers=True,
            forwarded_allow_ips=settings.trusted_proxy_ips,
        )
    elif args.command == "create-user":
        args.key_file.parent.mkdir(parents=True, exist_ok=True)
        # Create with private mode from the first byte; never print a secret to logs.
        import os

        fd = os.open(args.key_file, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            key = store.create_user(args.user, args.group, args.role)
            with os.fdopen(fd, "w") as f:
                fd = None
                f.write(key + "\n")
        except BaseException:
            if fd is not None:
                os.close(fd)
            args.key_file.unlink(missing_ok=True)
            raise
        print(f"Created {args.user}; API Key saved to {args.key_file.resolve()}")
    elif args.command == "rotate-key":
        try:
            store.rotate_key(args.user, args.key_file)
        except (OSError, ValueError, sqlite3.Error) as error:
            parser.exit(1, f"Key rotation failed: {error}\n")
        print(f"Key rotated; replacement saved to {args.key_file.resolve()}")
    elif args.command == "disable-user":
        store.disable_user(args.user)
        print("User disabled")
    elif args.command == "set-role":
        store.set_role(args.user, args.role)
        print("Role updated")
    elif args.command == "ingest":
        with store.connection() as db:
            if not db.execute(
                "SELECT 1 FROM users WHERE id=? AND active=1", (args.owner,)
            ).fetchone():
                parser.error("Owner must be an active user")
        if args.watch_seconds and args.watch_seconds < 10:
            parser.error("watch-seconds must be at least 10")
        while True:
            result = ingest(store, settings, args.owner, args.visibility, args.workspace)
            print(json.dumps(result), flush=True)
            if not args.watch_seconds:
                sys.exit(1 if result["failed"] else 0)
            time.sleep(args.watch_seconds)
    elif args.command == "delete-document":
        store.delete_document(args.document_id)
        print("Document removed")
    elif args.command == "backup":
        store.backup(args.destination)
        print(f"Backup: {args.destination.resolve()}")
    elif args.command == "snapshot":
        from .backup import create_snapshot

        try:
            result = create_snapshot(store, settings, args.destination)
        except (OSError, ValueError, sqlite3.Error) as error:
            parser.exit(1, f"备份操作未完成：{error}\n")
        print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
