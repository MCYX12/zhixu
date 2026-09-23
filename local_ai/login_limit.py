"""Bounded per-process login attempt limiter for the single-worker gateway."""

import math
import time
from collections import deque

from starlette.responses import JSONResponse


class LoginLimit:
    def __init__(self, app, clock=time.monotonic, limit=10, window=60, max_clients=4096):
        self.app = app
        self.clock = clock
        self.limit = limit
        self.window = window
        self.max_clients = max_clients
        self.clients = {}

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["method"] != "POST" or scope["path"] != "/api/session":
            return await self.app(scope, receive, send)
        now = self.clock()
        for client, attempts in list(self.clients.items()):
            while attempts and attempts[0] <= now - self.window:
                attempts.popleft()
            if not attempts:
                del self.clients[client]
        # Uvicorn applies forwarded headers only from configured trusted proxies.
        # Do not read arbitrary X-Forwarded-For or CF-Connecting-IP here.
        peer = (scope.get("client") or ("unknown", 0))[0]
        attempts = self.clients.get(peer)
        if attempts is None and len(self.clients) < self.max_clients:
            attempts = self.clients[peer] = deque()
        if attempts is None or len(attempts) >= self.limit:
            retry = (
                self.window
                if attempts is None
                else max(1, math.ceil(attempts[0] + self.window - now))
            )
            return await JSONResponse(
                {
                    "error": {
                        "code": "login_rate_limited",
                        "message": f"登录尝试过于频繁，请在 {retry} 秒后重试",
                    }
                },
                status_code=429,
                headers={"Retry-After": str(retry), "Cache-Control": "no-store"},
            )(scope, receive, send)
        # No await between checking and reserving: concurrent ASGI requests cannot oversubscribe.
        attempts.append(now)
        await self.app(scope, receive, send)
