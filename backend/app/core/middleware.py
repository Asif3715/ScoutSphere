"""ASGI middleware: request guard (size cap, NUL characters) and security headers.

Pure ASGI (not BaseHTTPMiddleware) so request bodies can be inspected and replayed safely.
"""

import json
import re

from starlette.types import ASGIApp, Message, Receive, Scope, Send

MAX_BODY_BYTES = 1_048_576  # 1 MiB: far above any legitimate JSON payload in this API
# A JSON "\u0000" escape that is a real escape, not the text `\\u0000` (even number of
# backslashes before the backslash that starts the escape).
_NUL_ESCAPE = re.compile(rb"(?<!\\)(?:\\\\)*\\u0000")
_BODY_METHODS = {"POST", "PUT", "PATCH"}


def _json_response(status: int, code: str, message: str) -> tuple[Message, Message]:
    body = json.dumps({"error": {"code": code, "message": message}}).encode()
    start = {
        "type": "http.response.start",
        "status": status,
        "headers": [
            (b"content-type", b"application/json"),
            (b"content-length", str(len(body)).encode()),
        ],
    }
    return start, {"type": "http.response.body", "body": body}


class RequestGuardMiddleware:
    """Rejects requests PostgreSQL could never store or that are unreasonably large, with a
    clean 4xx instead of letting them reach the database (where they used to cause a 500)."""

    def __init__(self, app: ASGIApp, max_body: int = MAX_BODY_BYTES):
        self.app = app
        self.max_body = max_body

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        raw_target = scope.get("raw_path", b"") + b"?" + scope.get("query_string", b"")
        if b"%00" in raw_target or b"\x00" in raw_target:
            for message in _json_response(
                422, "invalid_characters", "Null characters are not allowed"
            ):
                await send(message)
            return

        if scope["method"] not in _BODY_METHODS:
            await self.app(scope, receive, send)
            return

        declared = dict(scope["headers"]).get(b"content-length")
        if declared and declared.isdigit() and int(declared) > self.max_body:
            for message in _json_response(413, "payload_too_large", "Request body is too large"):
                await send(message)
            return

        chunks: list[bytes] = []
        size = 0
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            chunk = message.get("body", b"")
            size += len(chunk)
            if size > self.max_body:
                for m in _json_response(413, "payload_too_large", "Request body is too large"):
                    await send(m)
                return
            chunks.append(chunk)
            if not message.get("more_body"):
                break
        body = b"".join(chunks)

        if b"\x00" in body or _NUL_ESCAPE.search(body):
            for m in _json_response(422, "invalid_characters", "Null characters are not allowed"):
                await send(m)
            return

        sent = False

        async def replay() -> Message:
            nonlocal sent
            if not sent:
                sent = True
                return {"type": "http.request", "body": body, "more_body": False}
            return await receive()

        await self.app(scope, replay, send)


class SecurityHeadersMiddleware:
    """Adds baseline hardening headers to every API response."""

    def __init__(self, app: ASGIApp, hsts: bool = False):
        self.app = app
        self.hsts = hsts

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = message.setdefault("headers", [])
                present = {k.lower() for k, _ in headers}
                extra = {
                    b"x-content-type-options": b"nosniff",
                    b"x-frame-options": b"DENY",
                    b"referrer-policy": b"no-referrer",
                    b"cache-control": b"no-store",
                    b"permissions-policy": b"camera=(), microphone=(), geolocation=()",
                }
                if self.hsts:
                    extra[b"strict-transport-security"] = b"max-age=31536000; includeSubDomains"
                for k, v in extra.items():
                    if k not in present:
                        headers.append((k, v))
            await send(message)

        await self.app(scope, receive, send_with_headers)
