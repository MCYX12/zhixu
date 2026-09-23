import hashlib
import json
import os
import secrets
import sqlite3
import time
from contextlib import closing, contextmanager
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class User:
    id: str
    groups: tuple[str, ...] = ()
    role: str = "member"


def key_hash(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


class Store:
    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with self.connection() as db:
            db.executescript("""
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS users (
              id TEXT PRIMARY KEY, groups_json TEXT NOT NULL, active INTEGER NOT NULL DEFAULT 1);
            CREATE TABLE IF NOT EXISTS api_keys (
              hash TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id),
              active INTEGER NOT NULL DEFAULT 1);
            CREATE TABLE IF NOT EXISTS documents (
              id TEXT PRIMARY KEY, source_root TEXT NOT NULL, path TEXT NOT NULL,
              sha256 TEXT NOT NULL, pipeline TEXT NOT NULL, version TEXT NOT NULL,
              owner_id TEXT NOT NULL, workspace_id TEXT, visibility TEXT NOT NULL,
              updated_at REAL NOT NULL, UNIQUE(source_root, path));
            CREATE TABLE IF NOT EXISTS chunks (
              id TEXT PRIMARY KEY, document_id TEXT NOT NULL REFERENCES documents(id)
              ON DELETE CASCADE, ordinal INTEGER NOT NULL, title TEXT NOT NULL, text TEXT NOT NULL);
            CREATE INDEX IF NOT EXISTS chunks_doc ON chunks(document_id);
            CREATE TABLE IF NOT EXISTS ingest_runs (
              id INTEGER PRIMARY KEY, source_root TEXT NOT NULL, started_at REAL NOT NULL,
              finished_at REAL, status TEXT NOT NULL, summary TEXT);
            CREATE TABLE IF NOT EXISTS ingest_errors (
              run_id INTEGER NOT NULL, path TEXT NOT NULL, error TEXT NOT NULL);
            """)
            columns = {row[1] for row in db.execute("PRAGMA table_info(users)")}
            if "role" not in columns:
                db.execute("ALTER TABLE users ADD COLUMN role TEXT NOT NULL DEFAULT 'member'")
        path.chmod(0o600)

    @contextmanager
    def connection(self):
        db = sqlite3.connect(self.path, timeout=15)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        try:
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    def create_user(self, user_id: str, groups: list[str], role: str = "member") -> str:
        if role not in {"admin", "member"}:
            raise ValueError("Invalid role")
        key = "lai_" + secrets.token_urlsafe(32)
        with self.connection() as db:
            db.execute(
                "INSERT INTO users(id, groups_json, role) VALUES (?, ?, ?)",
                (user_id, json.dumps(groups), role),
            )
            db.execute(
                "INSERT INTO api_keys(hash, user_id) VALUES (?, ?)", (key_hash(key), user_id)
            )
        return key

    def authenticate(self, key: str) -> User | None:
        with self.connection() as db:
            row = db.execute(
                """SELECT u.* FROM users u JOIN api_keys k ON u.id=k.user_id
                               WHERE k.hash=? AND k.active=1 AND u.active=1""",
                (key_hash(key),),
            ).fetchone()
        return User(row["id"], tuple(json.loads(row["groups_json"])), row["role"]) if row else None

    def rotate_key(self, user_id: str, destination: Path):
        """Persist a private replacement before committing revocation; never print keys."""
        destination.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            with self.connection() as db:
                db.execute("BEGIN IMMEDIATE")
                if not db.execute(
                    "SELECT 1 FROM users WHERE id=? AND active=1", (user_id,)
                ).fetchone():
                    raise ValueError("User must exist and be active")
                key = "lai_" + secrets.token_urlsafe(32)
                with os.fdopen(fd, "w") as handle:
                    fd = None
                    handle.write(key + "\n")
                    handle.flush()
                    os.fsync(handle.fileno())
                db.execute("UPDATE api_keys SET active=0 WHERE user_id=?", (user_id,))
                db.execute(
                    "INSERT INTO api_keys(hash,user_id) VALUES (?,?)", (key_hash(key), user_id)
                )
                tables = {
                    r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")
                }
                if "web_sessions" in tables:
                    db.execute("DELETE FROM web_sessions WHERE user_id=?", (user_id,))
                if "audit_events" in tables:
                    db.execute(
                        "INSERT INTO audit_events(user_id,action,target,created_at) VALUES (?,?,?,?)",
                        (user_id, "key.rotated", user_id, time.time()),
                    )
        except BaseException:
            if fd is not None:
                os.close(fd)
            destination.unlink(missing_ok=True)
            raise

    def disable_user(self, user_id: str):
        with self.connection() as db:
            db.execute("UPDATE users SET active=0 WHERE id=?", (user_id,))

    def set_role(self, user_id: str, role: str):
        if role not in {"admin", "member"}:
            raise ValueError("Invalid role")
        with self.connection() as db:
            if db.execute("UPDATE users SET role=? WHERE id=?", (role, user_id)).rowcount != 1:
                raise ValueError("Unknown user")

    @staticmethod
    def acl(user: User):
        placeholders = ",".join("?" for _ in user.groups) or "NULL"
        return (
            f"(d.owner_id=? OR d.visibility='public' OR "
            f"(d.visibility='group' AND d.workspace_id IN ({placeholders})))",
            [user.id, *user.groups],
        )

    def visible_chunks(self, user: User, chunk_id: str | None = None):
        acl, values = self.acl(user)
        query = (
            """SELECT c.*, d.path, d.visibility, d.version FROM chunks c
                   JOIN documents d ON c.document_id=d.id WHERE """
            + acl
        )
        if chunk_id:
            query += " AND c.id=?"
            values.append(chunk_id)
        with self.connection() as db:
            return [dict(r) for r in db.execute(query, values)]

    def document(self, document_id: str):
        with self.connection() as db:
            row = db.execute("SELECT * FROM documents WHERE id=?", (document_id,)).fetchone()
            return dict(row) if row else None

    def publish(self, doc: dict, chunks: list[dict]):
        # One transaction: readers see the complete previous or complete next version.
        with self.connection() as db:
            db.execute("DELETE FROM documents WHERE id=?", (doc["id"],))
            keys = list(doc)
            db.execute(
                f"INSERT INTO documents({','.join(keys)}) VALUES ({','.join('?' for _ in keys)})",
                [doc[k] for k in keys],
            )
            db.executemany(
                "INSERT INTO chunks VALUES (?,?,?,?,?)",
                [(c["id"], doc["id"], c["ordinal"], c["title"], c["text"]) for c in chunks],
            )

    def delete_document(self, document_id: str):
        with self.connection() as db:
            db.execute("DELETE FROM documents WHERE id=?", (document_id,))

    def start_run(self, root: str) -> int:
        with self.connection() as db:
            return db.execute(
                "INSERT INTO ingest_runs(source_root,started_at,status) VALUES (?,?,'running')",
                (root, time.time()),
            ).lastrowid

    def finish_run(self, run_id: int, summary: dict, errors: list[tuple[str, str]]):
        with self.connection() as db:
            db.execute(
                "UPDATE ingest_runs SET finished_at=?,status=?,summary=? WHERE id=?",
                (time.time(), "partial" if errors else "complete", json.dumps(summary), run_id),
            )
            db.executemany(
                "INSERT INTO ingest_errors VALUES (?,?,?)", [(run_id, p, e) for p, e in errors]
            )

    def backup(self, destination: Path):
        destination.parent.mkdir(parents=True, exist_ok=True)
        try:
            fd = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            raise ValueError("Backup destination already exists") from None
        os.close(fd)
        try:
            deadline = time.monotonic() + 120

            def progress(status, remaining, total):
                if time.monotonic() > deadline:
                    raise TimeoutError("Backup exceeded 120 seconds")

            with self.connection() as source, closing(sqlite3.connect(destination)) as target:
                source.backup(target, pages=256, progress=progress, sleep=0.05)
        except BaseException:
            destination.unlink(missing_ok=True)
            raise
