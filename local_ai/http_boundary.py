"""Small ASGI boundary: bounded request bodies and local-only browser assets."""

import json


class HTTPBoundary:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        async def secure_send(message):
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                headers.extend(
                    [
                        (b"x-content-type-options", b"nosniff"),
                        (b"referrer-policy", b"no-referrer"),
                        (b"cache-control", b"no-store"),
                        (
                            b"content-security-policy",
                            b"default-src 'self'; script-src 'self'; style-src 'self'; "
                            b"img-src 'self' data:; connect-src 'self'; font-src 'self'; "
                            b"object-src 'none'; frame-ancestors 'none'; base-uri 'none'",
                        ),
                    ]
                )
                message = dict(message, headers=headers)
            await send(message)

        if scope["method"] in {"POST", "PUT", "PATCH"}:
            limit = 5 * 1024 * 1024 if scope["path"] == "/api/documents" else 256 * 1024
            body = bytearray()
            while True:
                message = await receive()
                if message["type"] == "http.disconnect":
                    return
                body.extend(message.get("body", b""))
                if len(body) > limit:
                    data = json.dumps(
                        {
                            "error": {
                                "code": "body_too_large",
                                "message": "上传文件或请求超过大小限制",
                            }
                        }
                    ).encode()
                    await secure_send(
                        {
                            "type": "http.response.start",
                            "status": 413,
                            "headers": [(b"content-type", b"application/json")],
                        }
                    )
                    return await send({"type": "http.response.body", "body": data})
                if not message.get("more_body"):
                    break
            delivered = False

            async def replay():
                nonlocal delivered
                if not delivered:
                    delivered = True
                    return {"type": "http.request", "body": bytes(body), "more_body": False}
                return await receive()

            await self.app(scope, replay, secure_send)
        else:
            await self.app(scope, receive, secure_send)
