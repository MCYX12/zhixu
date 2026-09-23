"""Explicit public-query search and DNS-pinned, bounded public page retrieval."""

import asyncio
import ipaddress
import json
import re
import socket
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit, urlunsplit

import httpx

from .network_policy import SYSTEM_PROXY, NetworkPolicyError
from .proxy_fetch import proxy_response


class WebError(ValueError):
    pass


def search_terms(query):
    """Remove common Chinese request framing, using only the authorized current query."""
    query = query.strip()
    query = re.sub(
        r"^(?:请)?(?:帮我|为我)?(?:介绍一下|介绍|搜索一下|搜索|查找|查询|查一下)\s*", "", query
    )
    query = re.sub(r"(?:的)?(?:基本概况|基本情况|概况|简介|介绍)[。？?！!\s]*$", "", query)
    return query.strip() or ""


def relevant_result(query, title, snippet):
    """Conservative lexical guard, not a semantic relevance or fact verifier."""
    chunks = re.findall(r"[\u4e00-\u9fff]+|[a-zA-Z0-9]+", query.lower())
    terms = set()
    for chunk in chunks:
        if re.search(r"[\u4e00-\u9fff]", chunk):
            terms.update(chunk[i : i + 2] for i in range(len(chunk) - 1))
        elif len(chunk) > 2 and chunk not in {"the", "for", "and", "please"}:
            terms.add(chunk)
    text = (title + " " + snippet).lower()
    return not terms or sum(term in text for term in terms) / len(terms) >= 0.6


def public_url(value):
    if not isinstance(value, str) or len(value) > 2048 or any(ord(c) < 33 for c in value):
        raise WebError("Invalid public URL")
    try:
        u = urlsplit(value)
        if (
            u.scheme not in {"http", "https"}
            or not u.hostname
            or u.username is not None
            or u.password is not None
            or u.port not in {None, 80, 443}
            or "\\" in value
            or "%" in u.hostname
        ):
            raise ValueError()
        host = u.hostname.encode("idna").decode("ascii")
        if host.lower().rstrip(".") == "localhost" or host.lower().endswith(
            (".local", ".localhost")
        ):
            raise ValueError()
        try:
            address = ipaddress.ip_address(host)
        except ValueError:
            address = None
        if address is not None and not is_public(address):
            raise ValueError()
        return urlunsplit((u.scheme, u.netloc, u.path or "/", u.query, ""))
    except (ValueError, UnicodeError):
        raise WebError("Only public HTTP(S) pages are allowed") from None


def is_public(address):
    # Reject IPv6 transition mechanisms as well as special/private/mapped addresses.
    return address.is_global and not (
        address.is_multicast
        or (
            address.version == 6
            and (
                address.ipv4_mapped
                or address.sixtofour
                or address.teredo
                or address in ipaddress.ip_network("64:ff9b::/96")
                or address in ipaddress.ip_network("64:ff9b:1::/48")
            )
        )
    )


async def public_addresses(host, port):
    records = await asyncio.get_running_loop().getaddrinfo(host, port, type=socket.SOCK_STREAM)
    addresses = list(dict.fromkeys(r[4][0] for r in records))
    if not addresses or any(not is_public(ipaddress.ip_address(a)) for a in addresses):
        raise WebError("Destination resolves to a non-public address")
    return addresses


class PageText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.hidden = 0
        self.parts = []
        self.main_parts = []
        self.main_depth = 0
        self.article_parts = []
        self.article_depth = 0
        self.published = None

    def handle_starttag(self, tag, attrs):
        if tag in {"main", "article"}:
            self.main_depth += 1
        if tag == "article":
            self.article_depth += 1
        if tag in {"script", "style", "noscript", "svg", "nav", "footer", "header"}:
            self.hidden += 1
        attr = dict(attrs)
        if tag == "meta" and (attr.get("property") or attr.get("name")) in {
            "article:published_time",
            "datePublished",
            "date",
        }:
            self.published = (attr.get("content") or "")[:80] or None
        if tag in {"p", "br", "div", "li", "h1", "h2", "h3"} and not self.hidden:
            self.parts.append("\n")
            if self.main_depth:
                self.main_parts.append("\n")
            if self.article_depth:
                self.article_parts.append("\n")

    def handle_endtag(self, tag):
        if tag in {"main", "article"}:
            self.main_depth = max(0, self.main_depth - 1)
        if tag == "article":
            self.article_depth = max(0, self.article_depth - 1)
        if tag in {"script", "style", "noscript", "svg", "nav", "footer", "header"}:
            self.hidden = max(0, self.hidden - 1)

    def handle_data(self, data):
        if not self.hidden:
            self.parts.append(data)
            if self.main_depth:
                self.main_parts.append(data)
            if self.article_depth:
                self.article_parts.append(data)

    def text(self):
        parts = self.article_parts or self.main_parts or self.parts
        return "\n".join(
            " ".join(line.split()) for line in " ".join(parts).splitlines() if line.strip()
        )


def clean_text(text, limit):
    parser = PageText()
    parser.feed(str(text)[:100_000])
    return parser.text()[:limit]


async def bounded_body(response, limit):
    if response.headers.get("content-encoding", "identity").lower() not in {"identity", ""}:
        raise WebError("Compressed response not accepted")
    data = bytearray()
    async for chunk in response.aiter_raw():
        data.extend(chunk)
        if len(data) > limit:
            raise WebError("Response exceeds byte budget")
    return bytes(data)


class PublicFetcher:
    def __init__(self, resolver=public_addresses, transport=None, proxy_selector=None):
        self.resolver = resolver
        self.transport = transport
        self.proxy_selector = proxy_selector or (
            SYSTEM_PROXY.for_url if transport is None else lambda url: None
        )

    @asynccontextmanager
    async def response(self, url, host, port, address, headers):
        proxy = await asyncio.to_thread(self.proxy_selector, url)
        if proxy:
            response = await proxy_response(url, host, port, address, proxy, headers)
            try:
                yield response
            finally:
                await response.aclose()
        else:
            target = httpx.URL(url).copy_with(host=address)
            async with httpx.AsyncClient(
                trust_env=False, follow_redirects=False, timeout=6, transport=self.transport
            ) as client:
                async with client.stream(
                    "GET", target, headers=headers, extensions={"sni_hostname": host}
                ) as response:
                    yield response

    async def fetch(self, url):
        async with asyncio.timeout(8):
            for _ in range(3):
                url = public_url(url)
                parsed = urlsplit(url)
                host = parsed.hostname.encode("idna").decode("ascii")
                port = parsed.port or (443 if parsed.scheme == "https" else 80)
                addresses = await self.resolver(host, port)
                if not addresses or any(not is_public(ipaddress.ip_address(a)) for a in addresses):
                    raise WebError("Non-public DNS answer")
                headers = {
                    "Host": parsed.netloc,
                    "Accept-Encoding": "identity",
                    "Accept": "text/html,text/plain",
                    "User-Agent": "ZhixuResearch/0.3",
                }
                async with self.response(url, host, port, addresses[0], headers) as response:
                    if response.status_code in {301, 302, 303, 307, 308}:
                        url = urljoin(url, response.headers.get("location", ""))
                        continue
                    response.raise_for_status()
                    mime = response.headers.get("content-type", "").split(";")[0].lower()
                    if mime not in {"text/html", "text/plain", "application/xhtml+xml"}:
                        raise WebError("Unsupported page type")
                    raw = await bounded_body(response, 1_000_000)
                    text = raw.decode(response.encoding or "utf-8", errors="replace")
                    parser = PageText()
                    parser.feed(text)
                    content = parser.text() if mime != "text/plain" else text
                    if len(content.strip()) < 80:
                        raise WebError("No usable page text")
                    return {
                        "url": url,
                        "text": content[:2200],
                        "published_at": parser.published,
                    }
            raise WebError("Too many redirects")


class WebSearch:
    def __init__(self, settings, transport=None, fetcher=None, planner=None):
        self.settings = settings
        self.transport = transport
        self.fetcher = fetcher or PublicFetcher()
        self.planner = planner

    async def ready(self):
        try:
            async with httpx.AsyncClient(
                trust_env=False, timeout=2, transport=self.transport
            ) as client:
                response = await client.get(self.settings.searxng_url.rstrip("/") + "/config")
                return response.status_code == 200
        except httpx.HTTPError:
            return False

    async def search(self, query):
        results = await self._search(query)
        if results:
            return results
        # Retry an empty retrieval once, using only the explicitly public question.
        from .search_planner import alternate_query

        planner = self.planner or (alternate_query if self.transport is None else None)
        if planner:
            alternative = await planner(self.settings, query)
            if alternative and search_terms(alternative) != search_terms(query):
                return await self._search(alternative)
        return []

    async def _search(self, query):
        terms = search_terms(query) or query
        try:
            async with asyncio.timeout(25):
                if self.transport is None:
                    await asyncio.to_thread(SYSTEM_PROXY.for_url, "https://cn.bing.com/")
                async with httpx.AsyncClient(
                    trust_env=False, follow_redirects=False, timeout=12, transport=self.transport
                ) as client:
                    async with client.stream(
                        "POST",
                        self.settings.searxng_url.rstrip("/") + "/search",
                        data={
                            "q": terms,
                            "format": "json",
                            "categories": "general",
                            "language": "zh-CN"
                            if re.search(r"[\u4e00-\u9fff]", terms)
                            else "en-US",
                            "safesearch": "1",
                        },
                        headers={"Accept-Encoding": "identity", "X-Real-IP": "127.0.0.1"},
                    ) as response:
                        response.raise_for_status()
                        payload = json.loads(await bounded_body(response, 1_000_000))
                if not isinstance(payload, dict) or not isinstance(payload.get("results"), list):
                    raise WebError("Invalid search response")
                selected = []
                seen = set()
                for item in payload["results"][:30]:
                    if not isinstance(item, dict):
                        continue
                    if not relevant_result(
                        terms,
                        clean_text(item.get("title", ""), 240),
                        clean_text(item.get("content", ""), 1200),
                    ):
                        continue
                    try:
                        url = public_url(item.get("url"))
                    except WebError:
                        continue
                    if url in seen:
                        continue
                    seen.add(url)
                    selected.append(
                        {
                            "url": url,
                            "title": clean_text(item.get("title", url), 240),
                            "text": clean_text(item.get("content", ""), 1200),
                            "published_at": str(item.get("publishedDate") or "")[:80] or None,
                            "retrieved_at": datetime.now(UTC).isoformat(),
                            "kind": "web",
                            "coverage": "snippet",
                        }
                    )
                    if len(selected) == 3:
                        break
                if not selected and payload.get("unresponsive_engines"):
                    raise WebError("Search engines unavailable")

                async def enrich(item):
                    try:
                        page = await self.fetcher.fetch(item["url"])
                        item.update({"text": page["text"], "url": page["url"], "coverage": "page"})
                        item["published_at"] = page["published_at"] or item["published_at"]
                    except (
                        WebError,
                        NetworkPolicyError,
                        httpx.HTTPError,
                        OSError,
                        TimeoutError,
                        UnicodeError,
                        LookupError,
                    ):
                        pass  # Search snippet is explicitly labeled; never claim full-page access.
                    return item

                results = await asyncio.gather(*(enrich(item) for item in selected))
                return [r for r in results if r["text"].strip()]
        except NetworkPolicyError as error:
            raise WebError(str(error)) from error
        except (httpx.HTTPError, OSError, TimeoutError, ValueError) as error:
            raise WebError("搜索服务暂不可用，请检查本机 SearXNG 与网络后重试") from error
