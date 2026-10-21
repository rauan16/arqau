"""Rate limiting tests for the public /demo/ai/chat endpoint.

No live LLM or network access: every provider interaction is served by a
deterministic `FakeCopilotProvider`. The demo endpoint is public (no
authentication) and must remain read-only.

Tests cover:
- requests below the per-IP ceiling are allowed (HTTP 200);
- exceeding the ceiling returns HTTP 429 with a correct Retry-After header;
- the limit is enforced before the LLM provider is called;
- limits are independent per IP (unit level);
- read-only behaviour and deterministic fallback are preserved;
- spoofed X-Forwarded-For headers are ignored when TRUSTED_PROXY_COUNT=0,
  so the limit stays keyed by the immediate peer IP.
"""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

import httpx

from app.config import get_settings
from app.core.database import Base, configure_database, create_database
from app.core.rate_limit import (
    DEMO_AI_MAX_REQUESTS,
    DEMO_AI_WINDOW_SECONDS,
    get_demo_ai_limiter,
)
from app.database import get_db
from app.main import app
from app.schemas.ai_copilot import CopilotResponse
from app.services.ai_copilot import (
    FakeCopilotProvider,
    get_copilot_provider,
)

os.environ.setdefault("APP_ENV", "testing")
os.environ.setdefault("SECRET_KEY", "test-secret")
os.environ.setdefault("OPENAI_API_KEY", "")
os.environ.setdefault("OPENAI_MODEL", "gpt-4o-mini")

SAFE_CONTENT = {
    "response": "Доступно 120000 minor units.",
    "key_facts": [{"code": "available_amount", "text": "Доступно: 120000 minor units."}],
    "suggested_questions": [],
}

BACKEND_ROOT = Path(__file__).resolve().parents[1]


class DemoAIRateLimitTests(unittest.IsolatedAsyncioTestCase):
    """Integration tests for IP-based rate limiting on POST /demo/ai/chat."""

    async def asyncSetUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        database_path = Path(self.temp_dir.name) / "demo_ai_rate_limit.db"
        self.database_url = f"sqlite+aiosqlite:///{database_path.as_posix()}"
        self.original_url = get_settings().database_url
        self.engine, self.sessions = create_database(self.database_url)
        await configure_database(self.database_url)
        async with self.engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

        async def override_db():
            async with self.sessions() as session:
                yield session

        app.dependency_overrides[get_db] = override_db
        self.fake = FakeCopilotProvider(response=SAFE_CONTENT)
        app.dependency_overrides[get_copilot_provider] = lambda: self.fake
        self.client = httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://testserver",
        )

    async def asyncTearDown(self) -> None:
        await self.client.aclose()
        app.dependency_overrides.clear()
        await self.engine.dispose()
        self.temp_dir.cleanup()
        if self.original_url:
            await configure_database(self.original_url)

    async def _chat(self, message: str) -> httpx.Response:
        return await self.client.post("/demo/ai/chat", json={"message": message})

    async def test_allows_requests_below_threshold(self) -> None:
        for i in range(DEMO_AI_MAX_REQUESTS):
            resp = await self._chat(f"message {i}")
            self.assertEqual(resp.status_code, 200, f"request {i}: {resp.text}")

    async def test_blocks_at_threshold_returns_429(self) -> None:
        for i in range(DEMO_AI_MAX_REQUESTS):
            await self._chat(f"msg {i}")

        resp = await self._chat("one more")
        self.assertEqual(resp.status_code, 429, resp.text)
        self.assertIn("Retry-After", resp.headers)
        retry_after = int(resp.headers["Retry-After"])
        self.assertGreater(retry_after, 0)

    async def test_retry_after_is_within_window(self) -> None:
        for i in range(DEMO_AI_MAX_REQUESTS):
            await self._chat(f"msg {i}")

        resp = await self._chat("blocked")
        self.assertEqual(resp.status_code, 429)
        retry_after = int(resp.headers["Retry-After"])
        self.assertLessEqual(retry_after, DEMO_AI_WINDOW_SECONDS)

    async def test_limit_applied_before_provider(self) -> None:
        # Exhaust the IP ceiling; the fake provider must never be invoked.
        for i in range(DEMO_AI_MAX_REQUESTS):
            await self._chat(f"msg {i}")

        before = self.fake.call_count
        resp = await self._chat("should not reach provider")
        self.assertEqual(resp.status_code, 429)
        self.assertEqual(self.fake.call_count, before)

    async def test_independent_buckets_per_ip(self) -> None:
        # Different IPs have independent buckets (unit level).
        limiter = get_demo_ai_limiter()
        for _ in range(DEMO_AI_MAX_REQUESTS):
            await limiter.try_acquire("192.168.1.1")
        self.assertFalse(await limiter.try_acquire("192.168.1.1"))
        self.assertTrue(await limiter.try_acquire("192.168.1.2"))

    async def test_read_only_preserved(self) -> None:
        # Within the ceiling the endpoint behaves exactly as before: 200 and
        # read-only snapshot metadata preserved. Provider-generated vs fallback
        # depends on content validation and is covered by test_demo_ai.py.
        resp = await self._chat("How much is available?")
        self.assertEqual(resp.status_code, 200, resp.text)
        chat = CopilotResponse.model_validate(resp.json())
        self.assertTrue(chat.read_only)
        self.assertTrue(chat.snapshot_only)

    async def test_spoofed_forwarded_for_is_ignored(self) -> None:
        # With TRUSTED_PROXY_COUNT == 0 the limit uses request.client.host,
        # so forged X-Forwarded-For values do not create a new bucket.
        for i in range(DEMO_AI_MAX_REQUESTS):
            await self.client.post(
                "/demo/ai/chat",
                json={"message": f"msg {i}"},
                headers={"X-Forwarded-For": f"10.0.0.{i}"},
            )

        # All requests share one bucket regardless of forged headers.
        resp = await self.client.post(
            "/demo/ai/chat",
            json={"message": "blocked"},
            headers={"X-Forwarded-For": "99.99.99.99"},
        )
        self.assertEqual(resp.status_code, 429, resp.text)
        self.assertIn("Retry-After", resp.headers)


if __name__ == "__main__":
    unittest.main()
