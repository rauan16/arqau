"""HTTP request body size limit middleware (Phase 3.5.2B).

Enforces a global 64 KiB (65,536 bytes) limit on incoming request bodies.

Security requirements:
- Does not rely solely on Content-Length (client can omit or falsify it).
- Enforces limit against actual incoming body bytes from the ASGI receive stream.
- If Content-Length is present and clearly exceeds the limit, rejects early.
- Does not read an unbounded body into memory before checking its size.
- Preserves normal FastAPI/Starlette request-body behavior for allowed requests.

Ordering: this middleware MUST be added BEFORE any rate-limiting or
authentication middleware so that oversized requests are rejected before
consuming provider-attempt budgets or authenticated-user ceilings.
"""

from __future__ import annotations

import logging
from typing import Callable, Optional

from fastapi import Request, Response, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp, Message, Receive, Scope, Send

logger = logging.getLogger("arqau.body_limit")

BODY_LIMIT = 65_536  # 64 KiB


class _BodyLimitExceeded(Exception):
    """Raised when the request body exceeds the configured limit."""

    def __init__(self, received: int, limit: int) -> None:
        self.received = received
        self.limit = limit
        super().__init__(f"Request body exceeds {limit} bytes (received {received})")


def _extract_body_limit_exceeded(exc: BaseException) -> Optional[_BodyLimitExceeded]:
    """Extract _BodyLimitExceeded from an exception or ExceptionGroup."""
    if isinstance(exc, _BodyLimitExceeded):
        return exc
    if isinstance(exc, BaseExceptionGroup):
        for sub in exc.exceptions:
            found = _extract_body_limit_exceeded(sub)
            if found is not None:
                return found
    return None


class _BufferedReceive:
    """A receive callable that replays buffered body chunks."""

    def __init__(self, chunks: list[bytes]):
        self._chunks = chunks
        self._index = 0

    async def __call__(self) -> Message:
        if self._index < len(self._chunks):
            chunk = self._chunks[self._index]
            self._index += 1
            return {
                "type": "http.request",
                "body": chunk,
                "more_body": self._index < len(self._chunks),
            }
        return {"type": "http.request", "body": b"", "more_body": False}


class BodyLimitMiddleware(BaseHTTPMiddleware):
    """Middleware that enforces a maximum request body size.

    This middleware reads the request body from the ASGI receive stream,
    counting bytes as they arrive. If the total exceeds the limit, it returns
    HTTP 413 Payload Too Large before any downstream app logic executes.
    For allowed requests, the body is buffered and replayed to the downstream app.
    """

    def __init__(
        self,
        app: ASGIApp,
        limit: int = BODY_LIMIT,
        *,
        exclude_paths: Optional[list[str]] = None,
    ) -> None:
        super().__init__(app)
        if limit <= 0:
            raise ValueError("limit must be positive")
        self._limit = limit
        self._exclude_paths = exclude_paths or ["/health"]

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        if scope.get("path") in self._exclude_paths:
            await self.app(scope, receive, send)
            return

        # Check Content-Length header for early rejection
        headers = scope.get("headers", [])
        content_length = None
        for name, value in headers:
            if name == b"content-length":
                try:
                    content_length = int(value.decode())
                    break
                except ValueError:
                    pass

        if content_length is not None and content_length > self._limit:
            logger.warning(
                "Request rejected: declared Content-Length %d exceeds limit %d",
                content_length,
                self._limit,
            )
            response = Response(
                content='{"detail":"Payload too large"}',
                status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                media_type="application/json",
            )
            await response(scope, receive, send)
            return

        # Stream the body, counting bytes
        body_chunks: list[bytes] = []
        bytes_received = 0

        async def limited_receive() -> Message:
            nonlocal bytes_received
            message = await receive()
            if message["type"] == "http.request":
                body = message.get("body", b"")
                bytes_received += len(body)
                if bytes_received > self._limit:
                    raise _BodyLimitExceeded(bytes_received, self._limit)
                body_chunks.append(body)
            return message

        try:
            # Consume the entire body through our limited receive
            while True:
                message = await limited_receive()
                if message["type"] == "http.request" and not message.get("more_body", False):
                    break
        except _BodyLimitExceeded as exc:
            logger.warning(
                "Request rejected: body size %d bytes exceeds limit %d bytes",
                exc.received,
                exc.limit,
            )
            response = Response(
                content='{"detail":"Payload too large"}',
                status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                media_type="application/json",
            )
            await response(scope, receive, send)
            return
        except BaseException as exc:
            limit_exc = _extract_body_limit_exceeded(exc)
            if limit_exc is not None:
                logger.warning(
                    "Request rejected: body size %d bytes exceeds limit %d bytes",
                    limit_exc.received,
                    limit_exc.limit,
                )
                response = Response(
                    content='{"detail":"Payload too large"}',
                    status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                    media_type="application/json",
                )
                await response(scope, receive, send)
                return
            raise

        # Body is within limit - replay buffered body to downstream app
        buffered_receive = _BufferedReceive(body_chunks)
        await self.app(scope, buffered_receive, send)