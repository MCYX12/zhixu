import hashlib
import math
import re
import time
from collections import Counter

from .config import Settings
from .store import Store, User

EXTENSIONS = {".md", ".txt", ".py", ".c", ".h", ".cpp", ".hpp", ".rs", ".yaml", ".yml"}


def terms(text: str) -> list[str]:
    # Keep exact technical identifiers; Chinese characters + bigrams form a transparent baseline.
    result = re.findall(r"[a-z0-9_]+", text.lower())
    for word in re.findall(r"[\u3400-\u9fff]+", text):
        result.extend(word)
        result.extend(word[i : i + 2] for i in range(len(word) - 1))
    return result


def split_text(text: str, size: int, overlap: int) -> list[dict]:
    text = text.replace("\r\n", "\n").strip()
    if not text:
        raise ValueError("empty_document")
    pieces = []
    start = 0
    title = ""
    while start < len(text):
        end = min(start + size, len(text))
        if end < len(text):
            boundary = text.rfind("\n\n", start + size // 2, end)
            if boundary > start:
                end = boundary + 2
        body = text[start:end].strip()
        headings = re.findall(r"^#{1,6}\s+(.+)$", body, re.MULTILINE)
        if headings:
            title = headings[0]
        if body:
            pieces.append({"ordinal": len(pieces), "title": title, "text": body})
        if end == len(text):
            break
        start = max(start + 1, end - overlap)
    return pieces


def ingest(
    store: Store, settings: Settings, owner: str, visibility: str, workspace: str | None = None
) -> dict:
    if visibility not in {"private", "group", "public"}:
        raise ValueError("Invalid visibility")
    if visibility == "group" and not workspace:
        raise ValueError("Group documents require workspace")
    root = settings.knowledge_root.resolve()
    run = store.start_run(str(root))
    summary = {"updated": 0, "unchanged": 0, "failed": 0, "skipped": 0, "run_id": run}
    errors = []
    pipeline = f"text-v1:chars={settings.chunk_chars}:overlap={settings.overlap_chars}"
    try:
        if not root.is_dir():
            raise ValueError("knowledge_root_unavailable")

        # No automatic deletion: a missing NAS mount must never erase the active index.
        def walk_error(error):
            raise error

        for directory, dirs, files in root.walk(on_error=walk_error, follow_symlinks=False):
            dirs[:] = [
                d for d in dirs if not d.startswith(".") and not (directory / d).is_symlink()
            ]
            for name in sorted(files):
                file = directory / name
                if name.startswith(".") or file.suffix.lower() not in EXTENSIONS:
                    summary["skipped"] += 1
                    continue
                relative = file.relative_to(root).as_posix()
                try:
                    if file.is_symlink() or not file.resolve().is_relative_to(root):
                        raise ValueError("symlink_not_allowed")
                    with file.open("rb") as handle:
                        raw = handle.read(settings.max_file_bytes + 1)
                    if len(raw) > settings.max_file_bytes:
                        raise ValueError("file_too_large")
                    sha = hashlib.sha256(raw).hexdigest()
                    doc_id = hashlib.sha256(f"{root}\0{relative}".encode()).hexdigest()
                    version = hashlib.sha256(f"{sha}:{pipeline}".encode()).hexdigest()[:20]
                    old = store.document(doc_id)
                    if old and all(
                        old[k] == v
                        for k, v in {
                            "sha256": sha,
                            "pipeline": pipeline,
                            "owner_id": owner,
                            "visibility": visibility,
                            "workspace_id": workspace,
                        }.items()
                    ):
                        summary["unchanged"] += 1
                        continue
                    text = raw.decode("utf-8")
                    if "\x00" in text:
                        raise ValueError("binary_document")
                    chunks = split_text(text, settings.chunk_chars, settings.overlap_chars)
                    for c in chunks:
                        c["id"] = hashlib.sha256(
                            f"{doc_id}:{version}:{c['ordinal']}".encode()
                        ).hexdigest()
                    store.publish(
                        {
                            "id": doc_id,
                            "source_root": str(root),
                            "path": relative,
                            "sha256": sha,
                            "pipeline": pipeline,
                            "version": version,
                            "owner_id": owner,
                            "workspace_id": workspace,
                            "visibility": visibility,
                            "updated_at": time.time(),
                        },
                        chunks,
                    )
                    summary["updated"] += 1
                except (OSError, ValueError) as error:
                    summary["failed"] += 1
                    errors.append((relative, type(error).__name__))
    except (OSError, ValueError) as error:
        summary["failed"] += 1
        errors.append((".", str(error) if isinstance(error, ValueError) else type(error).__name__))
    store.finish_run(run, summary, errors)
    return summary


def search(store: Store, user: User, query: str, limit: int = 5) -> list[dict]:
    rows = store.visible_chunks(user)  # ACL BEFORE retrieval and ranking.
    if not rows:
        return []
    query_terms = set(terms(query))
    if not query_terms:
        return []
    bags = [Counter(terms(r["text"])) for r in rows]
    lengths = [sum(bag.values()) for bag in bags]
    average = sum(lengths) / len(rows) or 1
    df = Counter(term for bag in bags for term in query_terms if term in bag)
    scored = []
    for row, bag, length in zip(rows, bags, lengths):
        score = 0.0
        for term in query_terms:
            frequency = bag[term]
            if frequency:
                idf = math.log(1 + (len(rows) - df[term] + 0.5) / (df[term] + 0.5))
                score += (
                    idf * frequency * 2.5 / (frequency + 1.5 * (0.25 + 0.75 * length / average))
                )
        if score:
            scored.append(row | {"score": score})
    return sorted(scored, key=lambda r: (-r["score"], r["id"]))[:limit]
