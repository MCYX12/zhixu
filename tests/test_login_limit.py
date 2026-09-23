from fastapi.testclient import TestClient
from starlette.responses import PlainTextResponse
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from local_ai.login_limit import LoginLimit


async def endpoint(scope, receive, send):
    if scope["type"] == "lifespan":
        await receive()
        await send({"type": "lifespan.startup.complete"})
        await receive()
        await send({"type": "lifespan.shutdown.complete"})
        return
    await PlainTextResponse("ok")(scope, receive, send)


def test_limit_expiry_and_unaffected_routes():
    now = [0]
    app = LoginLimit(endpoint, clock=lambda: now[0], limit=2)
    with TestClient(app) as client:
        assert client.post("/api/session").status_code == 200
        assert client.post("/api/session").status_code == 200
        r = client.post("/api/session")
        assert r.status_code == 429 and r.headers["retry-after"] == "60"
        assert client.get("/api/me").status_code == 200
        now[0] = 60
        assert client.post("/api/session").status_code == 200


def test_bounded_state_fails_closed():
    app = LoginLimit(endpoint, max_clients=1)
    with TestClient(app, client=("1.1.1.1", 1)) as c:
        assert c.post("/api/session").status_code == 200
    with TestClient(app, client=("2.2.2.2", 1)) as c:
        assert c.post("/api/session").status_code == 429
    assert len(app.clients) == 1


def test_spoofed_headers_cannot_reset_limit():
    app = ProxyHeadersMiddleware(LoginLimit(endpoint, limit=1), trusted_hosts=["127.0.0.1"])
    with TestClient(app, client=("203.0.113.1", 1)) as c:
        assert c.post("/api/session", headers={"X-Forwarded-For": "1.1.1.1"}).status_code == 200
        assert (
            c.post(
                "/api/session",
                headers={"X-Forwarded-For": "2.2.2.2", "CF-Connecting-IP": "2.2.2.2"},
            ).status_code
            == 429
        )


def test_trusted_proxy_separates_clients():
    app = ProxyHeadersMiddleware(LoginLimit(endpoint, limit=1), trusted_hosts=["127.0.0.1"])
    with TestClient(app, client=("127.0.0.1", 1)) as c:
        for ip in ["1.1.1.1", "2.2.2.2"]:
            assert c.post("/api/session", headers={"X-Forwarded-For": ip}).status_code == 200
        assert c.post("/api/session", headers={"X-Forwarded-For": "1.1.1.1"}).status_code == 429
