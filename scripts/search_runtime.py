"""Small integration adapter for pinned SearXNG; never edit its source checkout."""

import asyncio
import re
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit

from curl_cffi import CurlOpt

from local_ai.network_policy import SYSTEM_PROXY, NetworkPolicyError


def localized_search_url(url):
    parts = urlsplit(url)
    if parts.hostname not in {"www.bing.com", "cn.bing.com"} or parts.path != "/search":
        return url
    params = dict(parse_qsl(parts.query, keep_blank_values=True))
    if re.search(r"[\u4e00-\u9fff]", params.get("q", "")):
        params.update(setlang="zh-hans", cc="cn")
        return urlunsplit(parts._replace(query=urlencode(params)))
    return url


def install_system_proxy_adapter(network_class, selector=SYSTEM_PROXY.for_url):
    original = network_class.call_client

    async def call_client(self, stream, method, url, **kwargs):
        url = localized_search_url(url)
        # Select afresh for each engine request and redirect. Never fall back to direct
        # after a configured proxy fails. Known Bing regional redirects vary by VPN exit.
        for _ in range(4):
            kwargs.pop("proxies", None)
            kwargs["proxy"] = await asyncio.to_thread(selector, url) or ""
            kwargs["allow_redirects"] = False
            kwargs["curl_options"] = {
                **kwargs.get("curl_options", {}),
                CurlOpt.FRESH_CONNECT: 1,
                CurlOpt.FORBID_REUSE: 1,
                CurlOpt.DNS_CACHE_TIMEOUT: 0,
            }
            response = await original(self, stream, method, url, **kwargs)
            if stream or getattr(response, "status_code", 200) not in {301, 302, 303, 307, 308}:
                return response
            destination = urljoin(url, response.headers.get("location", ""))
            parsed = urlsplit(destination)
            if (
                parsed.scheme != "https"
                or parsed.hostname not in {"bing.com", "www.bing.com", "cn.bing.com"}
                or parsed.username
                or parsed.password
                or parsed.port not in {None, 443}
            ):
                raise NetworkPolicyError("搜索引擎重定向目标不在已验证范围内")
            if response.status_code == 303 or (
                response.status_code in {301, 302} and method.upper() == "POST"
            ):
                method = "GET"
                kwargs.pop("data", None)
            url = destination
        raise NetworkPolicyError("搜索引擎重定向次数超过预算")

    network_class.call_client = call_client


def main():
    from searx.network.network import Network

    install_system_proxy_adapter(Network)
    from searx.webapp import app
    from waitress import serve

    serve(app, host="127.0.0.1", port=8888, threads=4)


if __name__ == "__main__":
    main()
