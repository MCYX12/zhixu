import asyncio
import socket
import threading
import time

import httpx
import pytest
import uvicorn

from local_ai.api import create_app
from local_ai.config import Settings


class PausedStream(httpx.AsyncByteStream):
    def __init__(self, closed):
        self.closed = closed

    async def __aiter__(self):
        yield b'data: {"choices":[{"delta":{"content":"first"}}]}\n\n'
        await asyncio.sleep(30)
        yield b"data: [DONE]\n\n"

    async def aclose(self):
        self.closed.set()


@pytest.fixture
def running_server(tmp_path):
    closed = threading.Event()

    async def backend(request):
        return httpx.Response(
            200, headers={"content-type": "text/event-stream"}, stream=PausedStream(closed)
        )

    settings = Settings(
        database=tmp_path / "state.db",
        knowledge_root=tmp_path,
        max_concurrent=1,
        queue_timeout=5,
        allow_web_search=True,
        web_allowed_users=("alice",),
    )
    search_started, search_cancelled = threading.Event(), threading.Event()

    class PausedSearch:
        async def search(self, query):
            search_started.set()
            try:
                await asyncio.sleep(30)
                return []
            finally:
                search_cancelled.set()

    app = create_app(settings, httpx.MockTransport(backend), PausedSearch())
    app.state.search_started = search_started
    app.state.search_cancelled = search_cancelled
    keys = [app.state.store.create_user(name, []) for name in ("alice", "bob")]
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, log_level="error", access_log=False))
    thread = threading.Thread(target=server.run, kwargs={"sockets": [sock]}, daemon=True)
    thread.start()
    deadline = time.monotonic() + 5
    while not server.started:
        if time.monotonic() > deadline:
            raise RuntimeError("test server failed to start")
        time.sleep(0.01)
    try:
        yield f"http://127.0.0.1:{port}", app, keys, closed
    finally:
        server.should_exit = True
        thread.join(timeout=5)
        sock.close()
        assert not thread.is_alive()


async def wait_until(predicate):
    async with asyncio.timeout(2):
        while not predicate():
            await asyncio.sleep(0.01)


async def test_real_socket_disconnect_closes_upstream_and_releases_slot(running_server):
    url, app, keys, closed = running_server
    async with httpx.AsyncClient(base_url=url, trust_env=False) as client:
        async with client.stream(
            "POST",
            "/v1/chat/completions",
            headers={"Authorization": "Bearer " + keys[0]},
            json={
                "model": "local",
                "stream": True,
                "messages": [{"role": "user", "content": "hello"}],
            },
        ) as r:
            lines = r.aiter_lines()
            while "first" not in await anext(lines):
                pass
            assert app.state.queue.active == 1
        await wait_until(lambda: app.state.queue.active == 0)
        assert closed.is_set()
        assert not app.state.queue.users


async def test_disconnect_while_queued_removes_waiter(running_server):
    url, app, keys, closed = running_server
    body = {"model": "local", "stream": True, "messages": [{"role": "user", "content": "hello"}]}
    async with httpx.AsyncClient(base_url=url, trust_env=False) as client:
        async with client.stream(
            "POST",
            "/v1/chat/completions",
            headers={"Authorization": "Bearer " + keys[0]},
            json=body,
        ) as r:
            lines = r.aiter_lines()
            while "first" not in await anext(lines):
                pass
            second = asyncio.create_task(
                client.post(
                    "/v1/chat/completions",
                    json=body,
                    headers={"Authorization": "Bearer " + keys[1]},
                )
            )
            await wait_until(lambda: app.state.queue.waiting == 1)
            second.cancel()
            with pytest.raises(asyncio.CancelledError):
                await second
            await wait_until(lambda: app.state.queue.waiting == 0)
            assert app.state.queue.users == {"alice"}
        await wait_until(lambda: app.state.queue.active == 0)


async def test_disconnect_during_search_cancels_work_and_releases_slot(running_server):
    url, app, keys, closed = running_server
    async with httpx.AsyncClient(base_url=url, trust_env=False) as client:
        request = asyncio.create_task(
            client.post(
                "/v1/chat/completions",
                headers={"Authorization": "Bearer " + keys[0]},
                json={
                    "model": "web",
                    "web_query": "public test query",
                    "stream": True,
                    "messages": [{"role": "user", "content": "Summarize public sources"}],
                },
            )
        )
        await wait_until(app.state.search_started.is_set)
        request.cancel()
        with pytest.raises(asyncio.CancelledError):
            await request
        await wait_until(app.state.search_cancelled.is_set)
        await wait_until(lambda: app.state.queue.active == 0)
        assert not app.state.queue.users and not closed.is_set()
