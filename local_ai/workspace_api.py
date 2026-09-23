import asyncio
import json
import re
import time
from pathlib import Path
from typing import Literal
from urllib.parse import quote

import httpx
from fastapi import Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, ConfigDict, Field

from .backup import automatic_backup_status
from .network_policy import SYSTEM_PROXY
from .uploads import parse_document, upload_record


def fail(status, code, message):
    raise HTTPException(status, detail={"code": code, "message": message})


class AccessChange(BaseModel):
    model_config = ConfigDict(extra="forbid")
    visibility: Literal["private", "group", "public"]
    workspace_id: str | None = Field(default=None, max_length=64)


class MemberChange(BaseModel):
    model_config = ConfigDict(extra="forbid")
    role: Literal["admin", "member"]
    active: bool
    groups: list[str] = Field(default_factory=list, max_length=32)


class SavedMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")
    role: Literal["user", "assistant"]
    content: str = Field(max_length=20000)
    sources: list[dict] = Field(default_factory=list, max_length=20)


class ConversationSave(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=120)
    mode: Literal["auto", "local", "knowledge", "web"] = "auto"
    messages: list[SavedMessage] = Field(min_length=1, max_length=64)
    revision: int = Field(default=0, ge=0)


def register_workspace(app, settings, store, current_user):
    @app.get("/api/members")
    async def members(user=Depends(current_user)):
        if user.role != "admin":
            fail(403, "admin_required", "仅管理员可管理成员")
        return {"data": store.members()}

    @app.patch("/api/members/{member_id}")
    async def update_member(member_id: str, body: MemberChange, user=Depends(current_user)):
        if user.role != "admin":
            fail(403, "admin_required", "仅管理员可管理成员")
        if any(not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", group) for group in body.groups):
            fail(400, "invalid_groups", "组名仅支持1～64位字母、数字、下划线和短横线")
        try:
            store.update_member(user, member_id, body.role, body.groups, body.active)
        except PermissionError:
            fail(403, "admin_required", "管理员权限已失效")
        except LookupError:
            fail(404, "member_not_found", "成员不存在")
        except ValueError as error:
            fail(409, "member_conflict", str(error))
        return {"status": "ok"}

    uploading = set()
    parse_lock = asyncio.Lock()

    def check_access(user, visibility, workspace):
        if visibility == "public" and user.role != "admin":
            fail(403, "public_requires_admin", "仅管理员可以发布全员可见的资料")
        if visibility == "group" and (not workspace or workspace not in user.groups):
            fail(403, "group_not_allowed", "只能分享至你所属的团队")
        return workspace if visibility == "group" else None

    def document_for(user, document_id, manage=False):
        doc = store.visible_document(user, document_id)
        if not doc:
            fail(404, "document_not_found", "文档不存在或不可访问")
        if manage and not doc["can_manage"]:
            fail(403, "not_document_owner", "只有文档所有者或管理员可以管理此文档")
        return doc

    @app.post("/api/session")
    async def login(request: Request, user=Depends(current_user)):
        token, csrf = store.create_session(user)
        response = JSONResponse(
            {"user": {"id": user.id, "groups": user.groups, "role": user.role}, "csrf": csrf}
        )
        # HTTPS deployments should terminate TLS at the application / trusted proxy.
        response.set_cookie(
            "lai_session",
            token,
            max_age=8 * 3600,
            httponly=True,
            samesite="strict",
            path="/",
            secure=request.url.scheme == "https",
        )
        return response

    @app.delete("/api/session")
    async def logout(request: Request, user=Depends(current_user)):
        store.logout(request.cookies.get("lai_session", ""))
        response = JSONResponse({"ok": True})
        response.delete_cookie("lai_session", path="/")
        return response

    @app.get("/api/me")
    async def me(request: Request, user=Depends(current_user)):
        session = store.session(request.cookies.get("lai_session", ""))
        return {
            "user": {"id": user.id, "groups": user.groups, "role": user.role},
            "csrf": session[1] if session and session[0].id == user.id else None,
        }

    @app.get("/api/workspace")
    async def workspace(user=Depends(current_user)):
        docs = store.documents(user)
        conversations = store.conversation_list(user)
        with store.connection() as db:
            members = db.execute("SELECT COUNT(*) FROM users WHERE active=1").fetchone()[0]
        return {
            "documents": len(docs),
            "chunks": sum(d["chunk_count"] for d in docs),
            "conversations": len(conversations),
            "members": members if user.role == "admin" else None,
            "storage_bytes": sum(d["size"] for d in docs),
            "recent_documents": docs[:4],
            "external_access": settings.allow_web_search,
            "web_allowed": settings.allow_web_search and user.id in settings.web_allowed_users,
            "storage": "local",
            "model": "Qwen3.5 · 9B",
        }

    @app.get("/api/documents")
    async def documents(user=Depends(current_user)):
        return {"data": store.documents(user)}

    @app.get("/api/web-sources/{source_id}")
    async def web_source(source_id: str, user=Depends(current_user)):
        source = store.web_source(user, source_id)
        if not source:
            fail(404, "web_source_not_found", "联网来源不存在、已过期或不属于当前账号")
        return source

    @app.post("/api/documents", status_code=201)
    async def upload(
        request: Request,
        filename: str = Query(min_length=1, max_length=180),
        visibility: Literal["private", "group", "public"] = "private",
        workspace_id: str | None = Query(default=None, max_length=64),
        user=Depends(current_user),
    ):
        if filename != Path(filename).name or re.search(r"[\x00-\x1f/\\]", filename):
            fail(400, "invalid_filename", "请使用不含路径或控制字符的文件名")
        workspace_id = check_access(user, visibility, workspace_id)
        if user.id in uploading or parse_lock.locked():
            fail(429, "upload_busy", "有文档正在处理，请稍后再上传")
        uploading.add(user.id)
        try:
            async with parse_lock:
                owned = [d for d in store.documents(user) if d["owner_id"] == user.id]
                if len(owned) >= 200:
                    fail(409, "document_quota", "试点版每人最多 200 份文档，请先整理已有资料")
                raw = bytearray()
                async for chunk in request.stream():
                    raw.extend(chunk)
                    if len(raw) > min(settings.max_file_bytes, 5 * 1024 * 1024):
                        fail(413, "file_too_large", "单个文档不能超过 5 MB")
                if sum(d["size"] for d in owned) + len(raw) > 100 * 1024 * 1024:
                    fail(409, "storage_quota", "试点版每人文档上限为 100 MB")
                try:
                    pages = await parse_document(bytes(raw), filename)
                    doc = await asyncio.to_thread(
                        upload_record,
                        store,
                        settings,
                        user,
                        filename,
                        bytes(raw),
                        pages,
                        visibility,
                        workspace_id,
                    )
                except ValueError as error:
                    fail(422, "document_parse_failed", str(error))
                return doc
        finally:
            uploading.discard(user.id)

    @app.get("/api/documents/{document_id}")
    async def preview(document_id: str, user=Depends(current_user)):
        doc = document_for(user, document_id)
        chunks = [r for r in store.visible_chunks(user) if r["document_id"] == document_id]
        return doc | {"chunks": sorted(chunks, key=lambda r: r["ordinal"])}

    @app.get("/api/documents/{document_id}/download")
    async def download(document_id: str, user=Depends(current_user)):
        document_for(user, document_id)
        file = store.original(document_id)
        if not file:
            fail(404, "original_unavailable", "此文档来自旧版目录索引，没有上传原件")
        return Response(
            file["content"],
            media_type="application/octet-stream",
            headers={
                "Content-Disposition": "attachment; filename*=UTF-8''"
                + quote(file["filename"], safe="")
            },
        )

    @app.patch("/api/documents/{document_id}")
    async def access(document_id: str, body: AccessChange, user=Depends(current_user)):
        document_for(user, document_id, manage=True)
        workspace = check_access(user, body.visibility, body.workspace_id)
        store.update_access(user, document_id, body.visibility, workspace)
        return store.visible_document(user, document_id)

    @app.delete("/api/documents/{document_id}")
    async def delete(document_id: str, user=Depends(current_user)):
        document_for(user, document_id, manage=True)
        store.remove_upload(user, document_id)
        return {"ok": True}

    @app.get("/api/conversations")
    async def conversations(user=Depends(current_user)):
        return {"data": store.conversation_list(user)}

    def save(user, body, conversation_id=None):
        messages = [m.model_dump() for m in body.messages]
        if len(json.dumps(messages, ensure_ascii=False)) > 160000:
            fail(413, "conversation_too_large", "会话过长，请开始新对话")
        # Source details are untrusted client metadata; only persist IDs that are visible now.
        for message in messages:
            normalized = []
            for item in message["sources"]:
                if isinstance(item.get("web_id"), str):
                    source = store.web_source(user, item["web_id"])
                    if source:
                        normalized.append({k: v for k, v in source.items() if k != "text"})
                    continue
                chunk_id = item.get("chunk_id")
                if isinstance(chunk_id, str):
                    rows = store.visible_chunks(user, chunk_id)
                    if rows:
                        row = rows[0]
                        normalized.append(
                            {
                                "id": len(normalized) + 1,
                                "chunk_id": row["id"],
                                "path": row["path"],
                                "title": row["title"],
                                "url": f"/v1/sources/{row['id']}",
                            }
                        )
            message["sources"] = normalized
        try:
            return store.save_conversation(
                user, body.title, messages, body.mode, conversation_id, body.revision
            )
        except ValueError:
            fail(409, "conversation_conflict", "会话已更新或不可访问，请刷新后重试")

    @app.post("/api/conversations", status_code=201)
    async def create_conversation(body: ConversationSave, user=Depends(current_user)):
        return save(user, body)

    @app.get("/api/conversations/{conversation_id}")
    async def conversation(conversation_id: str, user=Depends(current_user)):
        result = store.conversation(user, conversation_id)
        if not result:
            fail(404, "conversation_not_found", "会话不存在或不可访问")
        # Revoked sources may not be opened. Saved answer text remains the owner's conversation.
        for message in result["messages"]:
            message["sources"] = [
                s
                for s in message.get("sources", [])
                if (
                    store.web_source(user, s["web_id"])
                    if s.get("web_id")
                    else store.visible_chunks(user, s.get("chunk_id", ""))
                )
            ]
        return result

    @app.put("/api/conversations/{conversation_id}")
    async def update_conversation(
        conversation_id: str, body: ConversationSave, user=Depends(current_user)
    ):
        return save(user, body, conversation_id)

    @app.delete("/api/conversations/{conversation_id}")
    async def delete_conversation(conversation_id: str, user=Depends(current_user)):
        if not store.remove_conversation(user, conversation_id):
            fail(404, "conversation_not_found", "会话不存在或不可访问")
        return {"ok": True}

    @app.get("/api/status")
    async def status(user=Depends(current_user)):
        start = time.monotonic()
        try:
            r = await app.state.client.get("models", timeout=3)
            r.raise_for_status()
            ready = bool(r.json().get("data"))
        except (httpx.HTTPError, ValueError):
            ready = False
        model_latency = round((time.monotonic() - start) * 1000)
        search_ready = await app.state.web_search.ready() if settings.allow_web_search else False
        return {
            "model_ready": ready,
            "model": "Qwen3.5-9B",
            "latency_ms": model_latency,
            "search_service_ready": search_ready,
            "web_network": await asyncio.to_thread(SYSTEM_PROXY.describe),
            "active": app.state.queue.active,
            "waiting": app.state.queue.waiting,
            "concurrency": settings.max_concurrent,
            "token_budget_enabled": settings.token_budget_enabled,
            "backup": automatic_backup_status() if user.role == "admin" else None,
            "queue_limit": settings.max_queue,
            "external_access": settings.allow_web_search,
            "web_allowed": settings.allow_web_search and user.id in settings.web_allowed_users,
            "storage": "local",
            "retrieval": "BM25",
            "version": "0.3.1",
            "events": store.events(user),
        }
