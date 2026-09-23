import asyncio
import json
import sqlite3
from dataclasses import replace

import httpx
import pytest
from fastapi.testclient import TestClient

from local_ai.api import create_app
from local_ai.config import Settings, load_settings
from local_ai.knowledge import ingest, search
from local_ai.queue import GenerationQueue, QueueError
from local_ai.store import Store, User


@pytest.fixture
def settings(tmp_path):
    root = tmp_path / "knowledge"
    root.mkdir()
    return Settings(
        database=tmp_path / "state.db", knowledge_root=root, queue_timeout=0.03, request_timeout=2
    )


def add_document(
    store, settings, text="TIM1 PWM MOE", visibility="private", owner="alice", workspace="lab"
):
    settings.knowledge_root.joinpath("test.md").write_text(text)
    return ingest(store, settings, owner, visibility, workspace)


def test_private_document_is_not_shared_by_group(settings):
    store = Store(settings.database)
    add_document(store, settings)
    assert search(store, User("alice"), "TIM1")
    assert not search(store, User("bob", ("lab",)), "TIM1")
    assert not search(store, User("bob"), "TIM1")


def test_group_and_public_documents(settings):
    store = Store(settings.database)
    add_document(store, settings, visibility="group")
    assert search(store, User("bob", ("lab",)), "TIM1")
    assert not search(store, User("eve"), "TIM1")
    add_document(store, settings, visibility="public")
    assert search(store, User("eve"), "TIM1")


def test_acl_change_without_content_change(settings):
    store = Store(settings.database)
    add_document(store, settings, visibility="public")
    assert search(store, User("bob"), "TIM1")
    result = add_document(store, settings, visibility="private")
    assert result["updated"] == 1
    assert not search(store, User("bob"), "TIM1")


def test_unchanged_and_pipeline_change(settings):
    store = Store(settings.database)
    assert add_document(store, settings)["updated"] == 1
    assert add_document(store, settings)["unchanged"] == 1
    assert add_document(store, replace(settings, chunk_chars=900))["updated"] == 1


def test_parse_failure_keeps_old_version(settings):
    store = Store(settings.database)
    add_document(store, settings)
    previous = store.visible_chunks(User("alice"))
    settings.knowledge_root.joinpath("test.md").write_bytes(b"\xff\xfe")
    result = ingest(store, settings, "alice", "private", "lab")
    assert result["failed"] == 1
    assert store.visible_chunks(User("alice")) == previous


def test_missing_mount_keeps_index(settings):
    store = Store(settings.database)
    add_document(store, settings)
    settings.knowledge_root.rename(settings.knowledge_root.with_name("unmounted"))
    assert ingest(store, settings, "alice", "private")["failed"] == 1
    assert search(store, User("alice"), "TIM1")


def test_missing_file_not_implicitly_deleted(settings):
    store = Store(settings.database)
    add_document(store, settings)
    settings.knowledge_root.joinpath("test.md").unlink()
    assert ingest(store, settings, "alice", "private")["failed"] == 0
    assert search(store, User("alice"), "TIM1")


def test_symlink_and_file_size_limit(settings, tmp_path):
    store = Store(settings.database)
    secret = tmp_path / "secret.md"
    secret.write_text("secret")
    settings.knowledge_root.joinpath("link.md").symlink_to(secret)
    assert ingest(store, settings, "alice", "private")["failed"] == 1
    settings.knowledge_root.joinpath("link.md").unlink()
    settings.knowledge_root.joinpath("huge.md").write_text("x" * 20)
    assert ingest(store, replace(settings, max_file_bytes=10), "alice", "private")["failed"] == 1
    assert not store.visible_chunks(User("alice"))


def test_atomic_publish_rollback(settings):
    store = Store(settings.database)
    add_document(store, settings)
    old = store.visible_chunks(User("alice"))
    doc = store.document(old[0]["document_id"])
    broken = [{"id": "duplicate", "ordinal": 0, "title": "", "text": "new"}] * 2
    with pytest.raises(sqlite3.IntegrityError):
        store.publish(doc, broken)
    assert store.visible_chunks(User("alice")) == old


def test_key_hash_revocation_and_backup(settings, tmp_path):
    store = Store(settings.database)
    key = store.create_user("alice", ["lab"])
    assert store.authenticate(key) == User("alice", ("lab",))
    assert not store.authenticate("invalid")
    with store.connection() as db:
        assert db.execute("SELECT hash FROM api_keys").fetchone()[0] != key
    add_document(store, settings)
    backup = tmp_path / "backup.db"
    store.backup(backup)
    restored = Store(backup)
    assert restored.authenticate(key)
    assert search(restored, User("alice"), "TIM1")
    store.disable_user("alice")
    assert not store.authenticate(key)


@pytest.mark.parametrize(
    "url",
    [
        "https://api.example.com/v1",
        "http://localhost:8080/v1",
        "http://192.168.1.2/v1",
        "http://127.0.0.1.evil.test/v1",
    ],
)
def test_external_backend_rejected(settings, url):
    with pytest.raises(ValueError):
        replace(settings, base_url=url)


def test_config_external_policy_fails_closed(tmp_path):
    cfg = tmp_path / "test.toml"
    cfg.write_text("[policy]\nallow_web_search = true\n")
    with pytest.raises(ValueError):
        load_settings(str(cfg))


async def test_queue_user_limit_capacity_and_release():
    queue = GenerationQueue(1, 1, 0.5)
    lease = await queue.acquire("a")
    with pytest.raises(QueueError) as duplicate:
        await queue.acquire("a")
    assert duplicate.value.code == "user_request_in_progress"
    waiting = asyncio.create_task(queue.acquire("b"))
    await asyncio.sleep(0.01)
    with pytest.raises(QueueError) as full:
        await queue.acquire("c")
    assert full.value.code == "queue_full"
    lease.release()
    lease.release()
    second = await waiting
    assert queue.active == 1
    second.release()
    assert queue.active == 0 and not queue.users


async def test_queue_timeout_and_cancellation():
    queue = GenerationQueue(1, 2, 0.03)
    lease = await queue.acquire("a")
    with pytest.raises(QueueError) as timed_out:
        await queue.acquire("b")
    assert timed_out.value.code == "queue_timeout"
    task = asyncio.create_task(queue.acquire("c"))
    await asyncio.sleep(0.005)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert queue.users == {"a"} and queue.waiting == 0
    lease.release()


class Backend:
    def __init__(self):
        self.requests = []
        self.status = 200
        self.truncated = False

    def __call__(self, request):
        self.requests.append(request)
        if request.url.path.endswith("/models"):
            return httpx.Response(self.status, json={"data": [{"id": "local-qwen"}]})
        if self.status != 200:
            return httpx.Response(self.status, text="private upstream details")
        body = json.loads(request.content)
        if body["stream"]:
            chunk = {
                "choices": [
                    {"index": 0, "delta": {"content": "检查 MOE [1]"}, "finish_reason": None}
                ]
            }
            text = "data: " + json.dumps(chunk) + "\n\n"
            if not self.truncated:
                text += "data: [DONE]\n\n"
            return httpx.Response(200, text=text, headers={"content-type": "text/event-stream"})
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": "检查 MOE [1]"},
                        "finish_reason": "stop",
                    }
                ]
            },
        )


@pytest.fixture
def client(settings):
    backend = Backend()
    app = create_app(settings, httpx.MockTransport(backend))
    key = app.state.store.create_user("alice", ["lab"])
    with TestClient(app) as client:
        client.headers["Authorization"] = "Bearer " + key
        yield client, app, backend


def post(client, mode="local", text="你好", stream=False, **extra):
    return client.post(
        "/v1/chat/completions",
        json={
            "model": mode,
            "stream": stream,
            "messages": [{"role": "user", "content": text}],
            **extra,
        },
    )


@pytest.mark.parametrize(
    "query",
    [
        "请帮我搜索 GitHub 上最近一周最热门的机器人相关仓库。",
        "你可以联网查找信息吗？",
        "请查找宇树在 GitHub 的官方仓库列表",
    ],
)
def test_local_search_requests_explain_explicit_web_mode(client, query):
    c, app, backend = client
    response = post(c, mode="auto", text=query)
    assert response.status_code == 200
    assert "公开搜索词" in response.json()["choices"][0]["message"]["content"]
    assert not backend.requests


def test_general_chat_receives_actual_capability_instruction(client):
    c, app, backend = client
    assert post(c, text="你好").status_code == 200
    payload = json.loads(backend.requests[-1].content)
    assert payload["messages"][0]["role"] == "system"
    assert "本次请求没有联网" in payload["messages"][0]["content"]


def test_auth_and_spoofed_identity(client):
    c, app, backend = client
    response = c.get(
        "/v1/models", headers={"Authorization": "Bearer fake", "X-OpenWebUI-User-Id": "alice"}
    )
    assert response.status_code == 401
    assert c.get("/v1/models").status_code == 200
    assert not backend.requests


@pytest.mark.parametrize("mode", ["web", "cloud"])
def test_disabled_routes_never_call_backend(client, mode):
    c, app, backend = client
    assert post(c, mode=mode).status_code == 403
    assert not backend.requests


def test_fresh_and_no_evidence_do_not_hallucinate(client):
    c, app, backend = client
    assert "无法核实" in post(c, text="今天最新消息").json()["choices"][0]["message"]["content"]
    assert (
        "没有找到"
        in post(c, mode="knowledge", text="TIM1").json()["choices"][0]["message"]["content"]
    )
    assert not backend.requests
    assert app.state.queue.active == 0


def test_chat_and_sources_and_acl(client, settings):
    c, app, backend = client
    add_document(app.state.store, settings)
    response = post(c, mode="knowledge", text="TIM1")
    assert response.status_code == 200
    sources = response.json()["sources"]
    assert sources and c.get(sources[0]["url"]).status_code == 200
    key = app.state.store.create_user("bob", ["lab"])
    assert c.get(sources[0]["url"], headers={"Authorization": "Bearer " + key}).status_code == 404
    payload = json.loads(backend.requests[-1].content)
    assert payload["model"] == "local-qwen"
    assert "MOE" in payload["messages"][0]["content"]
    assert app.state.queue.active == 0


def test_stream_and_truncated_stream_cleanup(client, settings):
    c, app, backend = client
    add_document(app.state.store, settings)
    response = post(c, mode="knowledge", text="TIM1", stream=True)
    assert response.status_code == 200
    assert '"sources"' in response.text and "[DONE]" in response.text
    assert app.state.queue.active == 0 and not app.state.queue.users
    backend.truncated = True
    response = post(c, stream=True)
    assert "upstream_stream_failed" in response.text
    assert app.state.queue.active == 0


def test_backend_error_sanitized_and_slot_released(client):
    c, app, backend = client
    backend.status = 500
    response = post(c)
    assert response.status_code == 503
    assert "private upstream" not in response.text
    assert app.state.queue.active == 0
    assert c.get("/ready").status_code == 503


def test_input_limits_and_unknown_fields(client):
    c, app, backend = client
    assert post(c, max_tokens=10000).status_code == 422
    assert post(c, text="x" * 16001).status_code == 422
    assert post(c, owner_id="other").status_code == 422
    assert not backend.requests


def test_chinese_and_exact_identifiers(settings):
    store = Store(settings.database)
    add_document(store, settings, text="机械臂抓取失败，检查末端夹爪。\nSTM32F103ZET6 TIM1 PA8")
    assert search(store, User("alice"), "抓取失败")
    assert search(store, User("alice"), "STM32F103ZET6")
    assert not search(store, User("alice"), "zzunknownzz")
