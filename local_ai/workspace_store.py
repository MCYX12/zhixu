"""Workspace persistence; migrations are additive to the original local index."""

import json
import secrets
import time
import uuid

from .store import Store, User, key_hash


class WorkspaceStore(Store):
    def __init__(self, path):
        super().__init__(path)
        with self.connection() as db:
            db.executescript("""
            CREATE TABLE IF NOT EXISTS web_sessions (
              token_hash TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id),
              csrf TEXT NOT NULL, expires_at REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS document_files (
              document_id TEXT PRIMARY KEY REFERENCES documents(id) ON DELETE CASCADE,
              content BLOB NOT NULL, size INTEGER NOT NULL, filename TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS conversations (
              id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id),
              title TEXT NOT NULL, messages_json TEXT NOT NULL, mode TEXT NOT NULL,
              created_at REAL NOT NULL, updated_at REAL NOT NULL, revision INTEGER NOT NULL);
            CREATE INDEX IF NOT EXISTS conversations_user ON conversations(user_id,updated_at);
            CREATE TABLE IF NOT EXISTS audit_events (
              id INTEGER PRIMARY KEY, user_id TEXT NOT NULL, action TEXT NOT NULL,
              target TEXT NOT NULL, created_at REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS web_sources (
              id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id),
              source_json TEXT NOT NULL, created_at REAL NOT NULL);
            """)

    @staticmethod
    def audit(db, user_id, action, target):
        db.execute(
            "INSERT INTO audit_events(user_id,action,target,created_at) VALUES (?,?,?,?)",
            (user_id, action, target, time.time()),
        )

    def members(self):
        with self.connection() as db:
            return [
                {
                    "id": r["id"],
                    "role": r["role"],
                    "active": bool(r["active"]),
                    "groups": json.loads(r["groups_json"]),
                }
                for r in db.execute("SELECT id,role,active,groups_json FROM users ORDER BY id")
            ]

    def update_member(self, actor, member_id, role, groups, active):
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            administrator = db.execute(
                "SELECT role,active FROM users WHERE id=?", (actor.id,)
            ).fetchone()
            if not administrator or administrator["role"] != "admin" or not administrator["active"]:
                raise PermissionError("admin_required")
            target = db.execute("SELECT * FROM users WHERE id=?", (member_id,)).fetchone()
            if not target:
                raise LookupError("member_not_found")
            if member_id == actor.id and (not active or role != "admin"):
                raise ValueError("不能停用自己或取消自己的管理员身份")
            if target["role"] == "admin" and target["active"] and (not active or role != "admin"):
                if (
                    db.execute(
                        "SELECT COUNT(*) FROM users WHERE role='admin' AND active=1"
                    ).fetchone()[0]
                    <= 1
                ):
                    raise ValueError("必须保留至少一名有效管理员")
            db.execute(
                "UPDATE users SET role=?,groups_json=?,active=? WHERE id=?",
                (role, json.dumps(sorted(set(groups))), int(active), member_id),
            )
            # Discard existing browser sessions on any account privilege change.
            db.execute("DELETE FROM web_sessions WHERE user_id=?", (member_id,))
            self.audit(db, actor.id, "member.updated", member_id)

    def save_web_sources(self, user, sources):
        result = []
        with self.connection() as db:
            # Bound local evidence retention; expired source references are filtered when loading saved chats.
            db.execute(
                "DELETE FROM web_sources WHERE user_id=? AND created_at<?",
                (user.id, time.time() - 30 * 86400),
            )
            for i, source in enumerate(sources, 1):
                sid = uuid.uuid4().hex
                item = source | {"id": i, "web_id": sid, "path": source["title"]}
                db.execute(
                    "INSERT INTO web_sources VALUES (?,?,?,?)",
                    (sid, user.id, json.dumps(item, ensure_ascii=False), time.time()),
                )
                result.append(item)
            self.audit(db, user.id, "web.search", str(len(result)))
        return result

    def web_source(self, user, source_id):
        with self.connection() as db:
            row = db.execute(
                "SELECT source_json FROM web_sources WHERE id=? AND user_id=? AND created_at>?",
                (source_id, user.id, time.time() - 30 * 86400),
            ).fetchone()
        return json.loads(row[0]) if row else None

    def create_session(self, user):
        token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(24)
        with self.connection() as db:
            db.execute("DELETE FROM web_sessions WHERE expires_at<?", (time.time(),))
            db.execute(
                "INSERT INTO web_sessions VALUES (?,?,?,?)",
                (key_hash(token), user.id, csrf, time.time() + 8 * 3600),
            )
            self.audit(db, user.id, "session.login", "")
        return token, csrf

    def session(self, token):
        with self.connection() as db:
            row = db.execute(
                """SELECT u.*,s.csrf FROM web_sessions s JOIN users u ON u.id=s.user_id
                                WHERE s.token_hash=? AND s.expires_at>? AND u.active=1""",
                (key_hash(token), time.time()),
            ).fetchone()
        if row:
            return User(row["id"], tuple(json.loads(row["groups_json"])), row["role"]), row["csrf"]
        return None

    def logout(self, token):
        with self.connection() as db:
            db.execute("DELETE FROM web_sessions WHERE token_hash=?", (key_hash(token),))

    def documents(self, user):
        acl, values = self.acl(user)
        with self.connection() as db:
            rows = db.execute(
                """SELECT d.id,d.path,d.owner_id,d.workspace_id,d.visibility,
                      d.version,d.updated_at,COALESCE(f.size,0) AS size,
                      CASE WHEN f.document_id IS NULL THEN 'indexed' ELSE 'upload' END AS origin,
                      (SELECT COUNT(*) FROM chunks c WHERE c.document_id=d.id) AS chunk_count
                      FROM documents d LEFT JOIN document_files f ON f.document_id=d.id
                      WHERE """
                + acl
                + " ORDER BY d.updated_at DESC",
                values,
            ).fetchall()
        return [
            dict(r) | {"can_manage": r["owner_id"] == user.id or user.role == "admin"} for r in rows
        ]

    def visible_document(self, user, document_id):
        return next((d for d in self.documents(user) if d["id"] == document_id), None)

    def publish_upload(self, doc, chunks, raw, actor):
        with self.connection() as db:
            keys = list(doc)
            db.execute(
                f"INSERT INTO documents({','.join(keys)}) VALUES ({','.join('?' for _ in keys)})",
                [doc[k] for k in keys],
            )
            db.executemany(
                "INSERT INTO chunks VALUES (?,?,?,?,?)",
                [(c["id"], doc["id"], c["ordinal"], c["title"], c["text"]) for c in chunks],
            )
            db.execute(
                "INSERT INTO document_files VALUES (?,?,?,?)",
                (doc["id"], raw, len(raw), doc["path"]),
            )
            self.audit(db, actor.id, "document.upload", doc["id"])

    def update_access(self, actor, document_id, visibility, workspace):
        with self.connection() as db:
            # Re-check ownership inside the write transaction.
            row = db.execute("SELECT * FROM documents WHERE id=?", (document_id,)).fetchone()
            if not row or (row["owner_id"] != actor.id and actor.role != "admin"):
                raise PermissionError("Document not manageable")
            db.execute(
                "UPDATE documents SET visibility=?,workspace_id=? WHERE id=?",
                (visibility, workspace, document_id),
            )
            self.audit(db, actor.id, "document.access_changed", document_id)

    def remove_upload(self, actor, document_id):
        with self.connection() as db:
            row = db.execute("SELECT owner_id FROM documents WHERE id=?", (document_id,)).fetchone()
            if not row or (row["owner_id"] != actor.id and actor.role != "admin"):
                raise PermissionError("Document not manageable")
            db.execute("DELETE FROM documents WHERE id=?", (document_id,))
            self.audit(db, actor.id, "document.deleted", document_id)

    def original(self, document_id):
        with self.connection() as db:
            row = db.execute(
                "SELECT content,filename FROM document_files WHERE document_id=?", (document_id,)
            ).fetchone()
            return dict(row) if row else None

    def conversation_list(self, user):
        with self.connection() as db:
            return [
                dict(r)
                for r in db.execute(
                    """SELECT id,title,mode,created_at,updated_at,revision
                 FROM conversations WHERE user_id=? ORDER BY updated_at DESC LIMIT 200""",
                    (user.id,),
                )
            ]

    def conversation(self, user, conversation_id):
        with self.connection() as db:
            row = db.execute(
                "SELECT * FROM conversations WHERE id=? AND user_id=?", (conversation_id, user.id)
            ).fetchone()
        if not row:
            return None
        result = dict(row)
        result["messages"] = json.loads(result.pop("messages_json"))
        return result

    def save_conversation(self, user, title, messages, mode, conversation_id=None, revision=0):
        now = time.time()
        with self.connection() as db:
            if conversation_id:
                cursor = db.execute(
                    """UPDATE conversations SET title=?,messages_json=?,mode=?,
                  updated_at=?,revision=revision+1 WHERE id=? AND user_id=? AND revision=?""",
                    (
                        title,
                        json.dumps(messages, ensure_ascii=False),
                        mode,
                        now,
                        conversation_id,
                        user.id,
                        revision,
                    ),
                )
                if cursor.rowcount != 1:
                    raise ValueError("conversation_conflict")
            else:
                conversation_id = uuid.uuid4().hex
                db.execute(
                    "INSERT INTO conversations VALUES (?,?,?,?,?,?,?,?)",
                    (
                        conversation_id,
                        user.id,
                        title,
                        json.dumps(messages, ensure_ascii=False),
                        mode,
                        now,
                        now,
                        1,
                    ),
                )
        return self.conversation(user, conversation_id)

    def remove_conversation(self, user, conversation_id):
        with self.connection() as db:
            return (
                db.execute(
                    "DELETE FROM conversations WHERE id=? AND user_id=?", (conversation_id, user.id)
                ).rowcount
                == 1
            )

    def events(self, user):
        with self.connection() as db:
            if user.role == "admin":
                rows = db.execute("SELECT * FROM audit_events ORDER BY id DESC LIMIT 50")
            else:
                rows = db.execute(
                    "SELECT * FROM audit_events WHERE user_id=? ORDER BY id DESC LIMIT 50",
                    (user.id,),
                )
            return [dict(r) for r in rows]
