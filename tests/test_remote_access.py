from dataclasses import replace

import pytest
from fastapi.testclient import TestClient
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from local_ai.api import create_app
from local_ai.config import Settings


@pytest.fixture
def remote(tmp_path):
    settings = Settings(tmp_path / "state.db", tmp_path, public_origin="https://ai.example.com")
    app = create_app(settings)
    key = app.state.store.create_user("alice", [])
    return app, key, settings


def test_trusted_proxy_login_and_csrf(remote):
    app, key, _ = remote
    proxy = ProxyHeadersMiddleware(app, trusted_hosts=["127.0.0.1"])
    with TestClient(proxy, base_url="https://ai.example.com", client=("127.0.0.1", 1234)) as client:
        headers = {
            "Authorization": "Bearer " + key,
            "X-Forwarded-Proto": "https",
            "Origin": "https://ai.example.com",
        }
        result = client.post("/api/session", headers=headers)
        assert result.status_code == 200
        assert "Secure" in result.headers["set-cookie"]
        assert client.get("/api/me").status_code == 200
        assert (
            client.delete(
                "/api/session",
                headers={"Origin": "https://evil.example", "X-CSRF-Token": result.json()["csrf"]},
            ).status_code
            == 403
        )
        assert (
            client.delete(
                "/api/session",
                headers={"Origin": "https://ai.example.com", "X-CSRF-Token": result.json()["csrf"]},
            ).status_code
            == 200
        )


def test_proxy_scheme_header_only_trusted_from_configured_peer(remote):
    app, _, _ = remote
    proxy = ProxyHeadersMiddleware(app, trusted_hosts=["127.0.0.1"])
    for peer, expected in [("203.0.113.5", 400), ("127.0.0.1", 200)]:
        with TestClient(proxy, base_url="http://ai.example.com", client=(peer, 1234)) as client:
            assert client.get("/", headers={"X-Forwarded-Proto": "https"}).status_code == expected


def test_unknown_host_and_loopback(remote):
    app, _, _ = remote
    with TestClient(app, client=("127.0.0.1", 1234)) as client:
        assert client.get("/", headers={"Host": "evil.example"}).status_code == 400
        assert client.get("/", headers={"Host": "127.0.0.1:9000"}).status_code == 200
    with TestClient(app, client=("203.0.113.5", 1234)) as client:
        assert client.get("/", headers={"Host": "127.0.0.1:9000"}).status_code == 400


@pytest.mark.parametrize(
    "origin",
    [
        "http://ai.example.com",
        "https://ai.example.com/path",
        "https://user:secret@ai.example.com",
        "https://ai.example.com?x=1",
    ],
)
def test_invalid_public_origin(remote, origin):
    with pytest.raises(ValueError):
        replace(remote[2], public_origin=origin)


def test_wildcard_proxy_rejected(remote):
    with pytest.raises(ValueError):
        replace(remote[2], trusted_proxy_ips="*")
