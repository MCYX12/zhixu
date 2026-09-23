"""Proxy transport preserving the validated destination IP and original TLS hostname."""

import httpx
from curl_cffi import CurlOpt, ffi, lib
from curl_cffi.requests import AsyncSession
from curl_cffi.requests.exceptions import RequestException


class Body(httpx.AsyncByteStream):
    def __init__(self, data):
        self.data = data

    async def __aiter__(self):
        yield self.data


def connect_rule(host, port, address):
    source = f"[{host}]" if ":" in host else host
    target = f"[{address}]" if ":" in address else address
    return f"{source}:{port}:{target}:{port}".encode()


async def proxy_response(url, host, port, address, proxy, headers, session_factory=AsyncSession):
    data = bytearray()
    exceeded = False

    def collect(chunk):
        nonlocal exceeded
        if len(data) + len(chunk) > 1_000_000:
            exceeded = True
            return 0  # Abort in the native transfer callback, without accumulating unbounded data.
        data.extend(chunk)
        return len(chunk)

    connection = lib.curl_slist_append(ffi.NULL, connect_rule(host, port, address))
    try:
        async with session_factory(
            trust_env=False,
            curl_options={
                CurlOpt.CONNECT_TO: connection,
                CurlOpt.MAXFILESIZE_LARGE: 1_000_000,
                CurlOpt.HTTP_CONTENT_DECODING: 0,
            },
        ) as session:
            response = await session.get(
                url,
                proxy=proxy,
                headers=headers,
                timeout=6,
                allow_redirects=False,
                content_callback=collect,
            )
            return httpx.Response(
                response.status_code,
                headers=dict(response.headers),
                stream=Body(bytes(data)),
                request=httpx.Request("GET", url),
            )
    except RequestException:
        message = "Response exceeds byte budget" if exceeded else "System proxy request failed"
        raise httpx.ProxyError(message) from None

    finally:
        lib.curl_slist_free_all(connection)
