import asyncio
from types import SimpleNamespace

import httpx
import pytest
from curl_cffi import CurlOpt, ffi
from curl_cffi.requests.exceptions import RequestException

from local_ai.network_policy import NetworkPolicyError, SystemProxy, bypass, read_system_proxy
from local_ai.proxy_fetch import connect_rule, proxy_response
from local_ai.web_search import PublicFetcher
from scripts.search_runtime import install_system_proxy_adapter, localized_search_url


def test_chinese_bing_query_keeps_subject_and_selects_chinese_market():
    from urllib.parse import parse_qs, urlsplit

    url = (
        "https://www.bing.com/search?q=%E8%8B%8F%E5%B7%9E%E5%B7%A5%E5%AD%A6%E9%99%A2&adlt=moderate"
    )
    params = parse_qs(urlsplit(localized_search_url(url)).query)
    assert params == {
        "q": ["苏州工学院"],
        "adlt": ["moderate"],
        "setlang": ["zh-hans"],
        "cc": ["cn"],
    }
    english = "https://www.bing.com/search?q=python"
    assert localized_search_url(english) == english


def settings(**extra):
    return {
        "HTTPEnable": "1",
        "HTTPProxy": "127.0.0.1",
        "HTTPPort": "7897",
        "HTTPSEnable": "1",
        "HTTPSProxy": "127.0.0.1",
        "HTTPSPort": "7897",
        **extra,
    }


def test_reads_scutil_without_shell_or_environment(monkeypatch):
    calls = []

    def run(args, **kwargs):
        calls.append((args, kwargs))
        return SimpleNamespace(
            stdout="""<dictionary> {
  HTTPSEnable : 1
  HTTPSProxy : 127.0.0.1
  HTTPSPort : 7897
  ExceptionsList : <array> {
    0 : *.local
    1 : 10.0.0.0/8
  }
}"""
        )

    monkeypatch.setattr("local_ai.network_policy.sys.platform", "darwin")
    monkeypatch.setattr("local_ai.network_policy.subprocess.run", run)
    result = read_system_proxy()
    assert result["exceptions"] == ["*.local", "10.0.0.0/8"]
    assert calls[0][0] == ["/usr/sbin/scutil", "--proxy"] and "shell" not in calls[0][1]


def test_system_changes_and_loopback_always_direct(monkeypatch):
    state = settings()
    policy = SystemProxy(lambda: dict(state))
    monkeypatch.setenv("HTTPS_PROXY", "http://unrelated.invalid:1234")
    assert policy.for_url("https://example.com") == "http://127.0.0.1:7897"
    state.update(HTTPSPort="7898")
    policy.updated = 0
    assert policy.for_url("https://example.com") == "http://127.0.0.1:7898"
    state.clear()
    policy.updated = 0
    assert policy.for_url("https://example.com") is None
    policy.reader = lambda: (_ for _ in ()).throw(NetworkPolicyError("Unavailable"))
    assert policy.for_url("http://127.0.0.1:8080/v1") is None
    assert policy.for_url("http://localhost:8888") is None
    assert policy.for_url("http://[::1]:9000") is None
    policy.updated = 0
    with pytest.raises(NetworkPolicyError):
        policy.for_url("https://example.com")


@pytest.mark.parametrize(
    "extra",
    [
        {"ProxyAutoConfigEnable": "1"},
        {"ProxyAutoDiscoveryEnable": "1"},
        {"HTTPSPort": "0"},
        {"HTTPSProxy": "user:secret@proxy"},
        {"HTTPSPort": "invalid"},
    ],
)
def test_unsupported_or_invalid_proxy_never_silently_direct(extra):
    policy = SystemProxy(lambda: settings(**extra))
    with pytest.raises(NetworkPolicyError):
        policy.for_url("https://example.com")
    assert policy.describe()["route"] == "unavailable"


def test_bypass_and_socks_selection():
    state = {
        "SOCKSEnable": "1",
        "SOCKSProxy": "127.0.0.1",
        "SOCKSPort": "1080",
        "exceptions": ["*.internal.example", "10.0.0.0/8", "<local>"],
    }
    policy = SystemProxy(lambda: state)
    assert policy.for_url("https://example.com") == "socks5h://127.0.0.1:1080"
    assert policy.for_url("https://test.internal.example") is None
    assert bypass("10.1.2.3", state)
    assert bypass("printer", state)
    assert not bypass("other.example", state)


async def test_search_engine_adapter_uses_current_proxy_each_request():
    seen = []

    class Network:
        async def call_client(self, stream, method, url, **kwargs):
            seen.append(kwargs)
            return "response"

    selected = ["http://127.0.0.1:7897", None]
    install_system_proxy_adapter(Network, lambda _: selected.pop(0))
    network = Network()
    await network.call_client(False, "GET", "https://cn.bing.com/search")
    await network.call_client(False, "GET", "https://cn.bing.com/search")
    assert [call["proxy"] for call in seen] == ["http://127.0.0.1:7897", ""]
    assert all(call["curl_options"][CurlOpt.FRESH_CONNECT] == 1 for call in seen)
    assert all(call["curl_options"][CurlOpt.FORBID_REUSE] == 1 for call in seen)
    assert all(call["curl_options"][CurlOpt.DNS_CACHE_TIMEOUT] == 0 for call in seen)


async def test_proxy_transfer_pins_ip_keeps_original_url_and_bounds_body():
    seen = []

    class Session:
        def __init__(self, **kwargs):
            rule = ffi.cast("struct curl_slist *", kwargs["curl_options"][CurlOpt.CONNECT_TO])
            seen.append(ffi.string(rule.data))
            assert kwargs["trust_env"] is False
            assert kwargs["curl_options"][CurlOpt.HTTP_CONTENT_DECODING] == 0

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def get(self, url, **kwargs):
            seen.append((url, kwargs["proxy"], kwargs["allow_redirects"]))
            assert kwargs["content_callback"](b"public data") == 11
            return SimpleNamespace(status_code=200, headers={"content-type": "text/html"})

    r = await proxy_response(
        "https://example.com/a",
        "example.com",
        443,
        "93.184.215.14",
        "http://127.0.0.1:7897",
        {},
        Session,
    )
    assert seen == [
        b"example.com:443:93.184.215.14:443",
        ("https://example.com/a", "http://127.0.0.1:7897", False),
    ]
    assert await r.aread() == b"public data"
    assert connect_rule("::1", 443, "2606:4700::1111") == b"[::1]:443:[2606:4700::1111]:443"


async def test_proxy_body_callback_aborts_over_budget():
    class Session:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def get(self, url, **kwargs):
            assert kwargs["content_callback"](b"x" * 1_000_001) == 0
            raise RequestException("aborted")

    with pytest.raises(httpx.ProxyError, match="byte budget"):
        await proxy_response(
            "https://example.com",
            "example.com",
            443,
            "93.184.215.14",
            "http://127.0.0.1:7897",
            {},
            Session,
        )


async def test_proxy_failure_does_not_retry_direct(monkeypatch):
    calls = []

    async def resolver(host, port):
        return ["93.184.215.14"]

    async def fail(*args):
        calls.append(args)
        raise httpx.ProxyError("unavailable")

    monkeypatch.setattr("local_ai.web_search.proxy_response", fail)
    with pytest.raises(httpx.ProxyError):
        await PublicFetcher(resolver, proxy_selector=lambda _: "http://127.0.0.1:1").fetch(
            "https://example.com"
        )
    assert len(calls) == 1


async def test_proxy_transfer_cancellation_closes_session():
    started, closed = asyncio.Event(), asyncio.Event()

    class Session:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            closed.set()

        async def get(self, *args, **kwargs):
            started.set()
            await asyncio.sleep(30)

    task = asyncio.create_task(
        proxy_response(
            "https://example.com",
            "example.com",
            443,
            "93.184.215.14",
            "http://127.0.0.1:7897",
            {},
            Session,
        )
    )
    await asyncio.wait_for(started.wait(), 1)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert closed.is_set()


async def test_bing_regional_redirect_uses_system_proxy_again():
    calls, selected = [], []

    class Network:
        async def call_client(self, stream, method, url, **kwargs):
            calls.append((url, kwargs))
            if len(calls) == 1:
                return SimpleNamespace(
                    status_code=301, headers={"location": "https://www.bing.com/search?q=test"}
                )
            return SimpleNamespace(status_code=200)

    def selector(url):
        selected.append(url)
        return "http://127.0.0.1:7897"

    install_system_proxy_adapter(Network, selector)
    result = await Network().call_client(False, "GET", "https://cn.bing.com/search?q=test")
    assert result.status_code == 200 and len(selected) == 2
    assert all(call[1]["allow_redirects"] is False for call in calls)


@pytest.mark.parametrize(
    "destination",
    [
        "http://127.0.0.1/",
        "https://example.com/",
        "https://u:p@www.bing.com/",
        "https://www.bing.com:9000/",
    ],
)
async def test_search_redirect_outside_known_engine_is_rejected(destination):
    class Network:
        async def call_client(self, *args, **kwargs):
            return SimpleNamespace(status_code=302, headers={"location": destination})

    install_system_proxy_adapter(Network, lambda _: None)
    with pytest.raises(NetworkPolicyError):
        await Network().call_client(False, "GET", "https://cn.bing.com/search")
