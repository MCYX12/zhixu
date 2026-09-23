"""Origin boundary for an explicitly configured HTTPS reverse proxy."""

from urllib.parse import urlsplit

from starlette.responses import JSONResponse


class RemoteBoundary:
    def __init__(self, app, public_origin):
        self.app = app
        self.public_host = urlsplit(public_origin).netloc.lower()

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        hosts = [
            value.decode("latin1").lower() for key, value in scope["headers"] if key == b"host"
        ]
        host = hosts[0] if len(hosts) == 1 else ""
        # Keep the existing loopback workbench and launcher health checks working.
        local_host = host.split(":")[0] in {"127.0.0.1", "localhost"}
        local_peer = scope.get("client", ("", 0))[0] in {"127.0.0.1", "::1"}
        if host != self.public_host and not (local_host and local_peer):
            return await JSONResponse(
                {"error": {"code": "host_rejected", "message": "访问域名未配置"}}, status_code=400
            )(scope, receive, send)
        if host == self.public_host and scope["scheme"] != "https":
            return await JSONResponse(
                {
                    "error": {
                        "code": "https_required",
                        "message": "远程访问必须使用 HTTPS；请检查可信代理配置",
                    }
                },
                status_code=400,
            )(scope, receive, send)
        await self.app(scope, receive, send)
