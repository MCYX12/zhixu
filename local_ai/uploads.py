import asyncio
import hashlib
import json
import sys
import time
import uuid
from pathlib import Path

from .knowledge import EXTENSIONS, split_text

SUPPORTED = EXTENSIONS | {".pdf", ".docx"}


async def parse_document(raw, filename):
    suffix = Path(filename).suffix.lower()
    if suffix not in SUPPORTED:
        raise ValueError("支持 PDF、DOCX、Markdown、TXT 和常见代码文件")
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        "-m",
        "local_ai.parser_worker",
        suffix,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL,
    )
    try:
        output, _ = await asyncio.wait_for(process.communicate(raw), timeout=20)
        if process.returncode:
            raise ValueError("解析失败或超过处理预算，请拆分文档后重试")
        result = json.loads(output)
        if "error" in result:
            raise ValueError(result["error"])
        return result["pages"]
    except TimeoutError:
        raise ValueError("解析超时，请拆分文档后重试") from None
    finally:
        if process.returncode is None:
            process.kill()
            await process.wait()


def upload_record(store, settings, user, filename, raw, pages, visibility, workspace):
    doc_id = uuid.uuid4().hex
    sha = hashlib.sha256(raw).hexdigest()
    version = sha[:20]
    chunks = []
    for page in pages:
        if not page["text"].strip():
            continue
        for chunk in split_text(page["text"], settings.chunk_chars, settings.overlap_chars):
            chunk["ordinal"] = len(chunks)
            chunk["id"] = hashlib.sha256(f"{doc_id}:{len(chunks)}".encode()).hexdigest()
            chunk["title"] = page["title"] or chunk["title"] or filename
            chunks.append(chunk)
    doc = {
        "id": doc_id,
        "source_root": "local-upload:" + user.id,
        "path": filename,
        "sha256": sha,
        "pipeline": "upload-text-v1",
        "version": version,
        "owner_id": user.id,
        "workspace_id": workspace,
        "visibility": visibility,
        "updated_at": time.time(),
    }
    # Different uploads with the same name get a version suffix, not an implicit destructive replace.
    with store.connection() as db:
        if db.execute(
            "SELECT 1 FROM documents WHERE source_root=? AND path=?", (doc["source_root"], filename)
        ).fetchone():
            doc["path"] = f"{Path(filename).stem} ({doc_id[:6]}){Path(filename).suffix}"
    store.publish_upload(doc, chunks, raw, user)
    return store.visible_document(user, doc_id)
