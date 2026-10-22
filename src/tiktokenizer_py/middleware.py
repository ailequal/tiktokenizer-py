"""ASGI middleware: rejects request bodies above the configured size before routing."""

from __future__ import annotations

from fastapi import status
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from tiktokenizer_py.errors import ApiError, error_response


class BodySizeLimitMiddleware:
    """Reject request bodies above ``max_bytes`` with 413, with or without Content-Length."""

    def __init__(self, app: ASGIApp, max_bytes: int) -> None:
        self.app = app
        self.max_bytes = max_bytes

    def _too_large(self) -> ApiError:
        return ApiError(
            status.HTTP_413_CONTENT_TOO_LARGE,
            "body_too_large",
            f"Request body is larger than {self.max_bytes:,} bytes",
            details={"limit": self.max_bytes},
        )

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        for key, value in scope["headers"]:
            if key == b"content-length" and value.isdigit() and int(value) > self.max_bytes:
                err = self._too_large()
                response = error_response(err.status_code, err.code, err.message, err.details)
                await response(scope, receive, send)
                return

        # No Content-Length (chunked upload): buffer up to the limit, then replay the body.
        chunks: list[bytes] = []
        size = 0
        while True:
            message = await receive()
            if message["type"] != "http.request":
                await self.app(scope, _replay([message]), send)
                return
            chunk = message.get("body", b"")
            size += len(chunk)
            if size > self.max_bytes:
                err = self._too_large()
                response = error_response(err.status_code, err.code, err.message, err.details)
                await response(scope, receive, send)
                return
            chunks.append(chunk)
            if not message.get("more_body", False):
                break

        body: Message = {"type": "http.request", "body": b"".join(chunks), "more_body": False}
        await self.app(scope, _replay([body], receive), send)


def _replay(messages: list[Message], then: Receive | None = None) -> Receive:
    """A receive callable that yields ``messages`` first, then defers to ``then``."""
    pending = list(messages)

    async def receive() -> Message:
        if pending:
            return pending.pop(0)
        if then is None:
            return {"type": "http.disconnect"}
        return await then()

    return receive
