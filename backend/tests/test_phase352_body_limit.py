"""Phase 3.5.2B BodyLimitMiddleware focused tests.

Tests the ASGI-level body size enforcement without network, providers, or sleeps.
Uses unittest.IsolatedAsyncioTestCase and direct ASGI receive control.
"""
import unittest
from starlette.types import ASGIApp, Receive, Scope, Send


BODY_LIMIT = 65_536  # 64 KiB


class FakeSend:
    def __init__(self):
        self.messages = []

    async def __call__(self, message):
        self.messages.append(message)


class _DownstreamApp:
    """Minimal downstream ASGI app that records execution and returns 200."""

    def __init__(self):
        self.called = False
        self.request_body = b""

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        self.called = True
        # Consume request body
        while True:
            msg = await receive()
            if msg["type"] == "http.request":
                self.request_body += msg.get("body", b"")
                if not msg.get("more_body", False):
                    break
            else:
                break
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"ok"})


class TestBodyLimitMiddleware(unittest.IsolatedAsyncioTestCase):
    """Direct ASGI-level tests for BodyLimitMiddleware."""

    def setUp(self):
        self.downstream = _DownstreamApp()
        from app.core.body_limit import BodyLimitMiddleware, BODY_LIMIT as BL
        self.middleware = BodyLimitMiddleware(app=self.downstream, limit=BL)
        self.send = FakeSend()

    def _make_scope(self, path="/test", headers=None):
        scope: Scope = {
            "type": "http",
            "method": "POST",
            "path": path,
            "headers": headers or [],
        }
        return scope

    def _make_receive(self, chunks: list[bytes]):
        """Create a receive callable that yields the given body chunks."""
        chunks_iter = iter(chunks)

        async def receive() -> dict:
            try:
                chunk = next(chunks_iter)
                return {"type": "http.request", "body": chunk, "more_body": True}
            except StopIteration:
                return {"type": "http.request", "body": b"", "more_body": False}

        return receive

    async def _call_middleware(self, scope, receive, send):
        await self.middleware(scope, receive, send)
        return send.messages

    def _get_response_status(self, messages):
        for msg in messages:
            if msg["type"] == "http.response.start":
                return msg["status"]
        return None

    def _get_response_body(self, messages):
        body = b""
        for msg in messages:
            if msg["type"] == "http.response.body":
                body += msg.get("body", b"")
        return body

    # --- Boundary tests ---

    async def test_exactly_65536_bytes_allowed(self):
        """Exactly 65,536 bytes should pass through."""
        body = b"x" * BODY_LIMIT
        scope = self._make_scope()
        receive = self._make_receive([body])
        messages = await self._call_middleware(scope, receive, self.send)
        status = self._get_response_status(messages)
        self.assertEqual(status, 200)

    async def test_65537_bytes_rejected(self):
        """65,537 bytes should return 413."""
        body = b"x" * (BODY_LIMIT + 1)
        scope = self._make_scope()
        receive = self._make_receive([body])
        messages = await self._call_middleware(scope, receive, self.send)
        status = self._get_response_status(messages)
        self.assertEqual(status, 413)
        body_bytes = self._get_response_body(messages)
        self.assertEqual(body_bytes, b'{"detail":"Payload too large"}')

    async def test_empty_body_allowed(self):
        """Empty body should pass through."""
        scope = self._make_scope()
        receive = self._make_receive([b""])
        messages = await self._call_middleware(scope, receive, self.send)
        status = self._get_response_status(messages)
        self.assertEqual(status, 200)

    async def test_small_json_allowed(self):
        """Normal small JSON body should pass."""
        body = b'{"key": "value"}'
        scope = self._make_scope()
        receive = self._make_receive([body])
        messages = await self._call_middleware(scope, receive, self.send)
        status = self._get_response_status(messages)
        self.assertEqual(status, 200)

    # --- Content-Length behavior ---

    async def test_oversized_without_content_length_rejected(self):
        """Oversized body without Content-Length header should be rejected."""
        body = b"x" * (BODY_LIMIT + 1)
        scope = self._make_scope(headers=[])
        receive = self._make_receive([body])
        messages = await self._call_middleware(scope, receive, self.send)
        status = self._get_response_status(messages)
        self.assertEqual(status, 413)

    async def test_falsified_small_content_length_bypassed(self):
        """Small Content-Length with large actual body should still be rejected."""
        body = b"x" * (BODY_LIMIT + 1)
        headers = [(b"content-length", b"100")]
        scope = self._make_scope(headers=headers)
        receive = self._make_receive([body])
        messages = await self._call_middleware(scope, receive, self.send)
        status = self._get_response_status(messages)
        self.assertEqual(status, 413)

    async def test_content_length_over_limit_rejected_early(self):
        """Declared Content-Length > limit should be rejected early."""
        headers = [(b"content-length", str(BODY_LIMIT + 1).encode())]
        scope = self._make_scope(headers=headers)
        receive = self._make_receive([b"small"])
        messages = await self._call_middleware(scope, receive, self.send)
        status = self._get_response_status(messages)
        self.assertEqual(status, 413)

    # --- Streaming / multi-chunk behavior ---

    async def test_multi_chunk_cumulative_exceeds_limit(self):
        """Multiple chunks whose total exceeds limit should be rejected."""
        chunk1 = b"x" * (BODY_LIMIT // 2)
        chunk2 = b"y" * (BODY_LIMIT // 2 + 1)
        scope = self._make_scope()
        receive = self._make_receive([chunk1, chunk2])
        messages = await self._call_middleware(scope, receive, self.send)
        status = self._get_response_status(messages)
        self.assertEqual(status, 413)

    async def test_multi_chunk_within_limit_allowed(self):
        """Multiple chunks whose total is within limit should pass."""
        chunk1 = b"x" * (BODY_LIMIT // 3)
        chunk2 = b"y" * (BODY_LIMIT // 3)
        chunk3 = b"z" * (BODY_LIMIT // 3)
        scope = self._make_scope()
        receive = self._make_receive([chunk1, chunk2, chunk3])
        messages = await self._call_middleware(scope, receive, self.send)
        status = self._get_response_status(messages)
        self.assertEqual(status, 200)

    # --- Response safety ---

    async def test_response_does_not_echo_body(self):
        """413 response must not contain the submitted body."""
        # Send enough data to exceed the limit
        body = b"x" * (BODY_LIMIT + 100)
        scope = self._make_scope()
        receive = self._make_receive([body])
        messages = await self._call_middleware(scope, receive, self.send)
        response_body = self._get_response_body(messages)
        self.assertNotIn(b"secret-data-should-not-leak", response_body)
        self.assertEqual(response_body, b'{"detail":"Payload too large"}')

    async def test_response_is_deterministic(self):
        """All 413 responses should be identical."""
        for _ in range(5):
            body = b"x" * (BODY_LIMIT + 1)
            scope = self._make_scope()
            receive = self._make_receive([body])
            send = FakeSend()
            await self._call_middleware(scope, receive, send)
            resp_body = self._get_response_body(send.messages)
            self.assertEqual(resp_body, b'{"detail":"Payload too large"}')


class TestBodyLimitMiddlewareHandlerExecution(unittest.IsolatedAsyncioTestCase):
    """Verify handler is not executed for rejected requests."""

    def setUp(self):
        from app.core.body_limit import BodyLimitMiddleware, BODY_LIMIT as BL
        self.downstream = _DownstreamApp()
        self.middleware = BodyLimitMiddleware(app=self.downstream, limit=BL)

    async def test_handler_not_called_on_rejection(self):
        """Endpoint handler should not be invoked after 413."""
        send = FakeSend()
        body = b"x" * (BODY_LIMIT + 1)
        scope = {"type": "http", "method": "POST", "path": "/test", "headers": []}
        receive = self._make_receive([body])
        await self.middleware(scope, receive, send)

        self.assertFalse(self.downstream.called, "Handler was called despite oversized body")
        status = None
        for msg in send.messages:
            if msg["type"] == "http.response.start":
                status = msg["status"]
        self.assertEqual(status, 413)

    def _make_receive(self, chunks):
        chunks_iter = iter(chunks)

        async def receive():
            try:
                chunk = next(chunks_iter)
                return {"type": "http.request", "body": chunk, "more_body": True}
            except StopIteration:
                return {"type": "http.request", "body": b"", "more_body": False}

        return receive


if __name__ == "__main__":
    unittest.main()