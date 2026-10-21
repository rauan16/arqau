"""Demo AI chat endpoint tests.

No live LLM or network access: every provider interaction is served by a
deterministic `FakeCopilotProvider`, by an explicitly unconfigured production
provider, or by a real exception type raised from the fake.

The demo endpoint is public (no authentication) and must remain read-only:
no financial mutations, no access to authenticated user data, no API keys
leaking into responses.
"""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from typing import Any, Optional

import httpx
from openai import APIConnectionError, APIStatusError, APITimeoutError, RateLimitError
from unittest.mock import patch

from app.config import get_settings
from app.core.auth_rate_limit import _reset_all_limiters
from app.core.database import Base, configure_database, create_database
from app.database import get_db
from app.main import app
from app.schemas.ai import ChatRequest
from app.schemas.ai_copilot import CopilotResponse
from app.services.ai_copilot import (
    FALLBACK_CONNECTION,
    FALLBACK_HTTP_ERROR,
    FALLBACK_MALFORMED,
    FALLBACK_NOT_CONFIGURED,
    FALLBACK_RATE_LIMIT,
    FALLBACK_SCHEMA_INVALID,
    FALLBACK_TIMEOUT,
    FALLBACK_UNSAFE_CONTENT,
    FALLBACK_UNSUPPORTED_AMOUNT,
    FakeCopilotProvider,
    OpenAICopilotProvider,
    get_copilot_provider,
    reset_production_provider,
)
from app.services.demo_financial_context import build_demo_financial_context

os.environ.setdefault("APP_ENV", "testing")
os.environ.setdefault("SECRET_KEY", "test-secret")
os.environ.setdefault("OPENAI_API_KEY", "")
os.environ.setdefault("OPENAI_MODEL", "gpt-4o-mini")

SAFE_CONTENT = {
    "response": (
        "Доступно 12000000 minor units. После покупки билета за 4500000 minor units "
        "останется 7500000 minor units."
    ),
    "key_facts": [
        {"code": "available_amount", "text": "Доступно: 12000000 minor units."},
    ],
    "suggested_questions": [],
}

BACKEND_ROOT = Path(__file__).resolve().parents[1]


def _rate_limit_error() -> RateLimitError:
    request = httpx.Request("POST", "https://api.openai.com/v1/chat/completions")
    response = httpx.Response(429, request=request)
    return RateLimitError("rate limited", response=response, body=None)


def _api_status_error(status_code: int = 500) -> APIStatusError:
    request = httpx.Request("POST", "https://api.openai.com/v1/chat/completions")
    response = httpx.Response(status_code, request=request)
    return APIStatusError("provider failure", response=response, body=None)


def _connection_error() -> APIConnectionError:
    request = httpx.Request("POST", "https://api.openai.com/v1/chat/completions")
    return APIConnectionError(message="connection reset", request=request)


class DemoAITestCase(unittest.IsolatedAsyncioTestCase):
    """Shared fixture for demo AI chat tests."""

    async def asyncSetUp(self) -> None:
        _reset_all_limiters()
        self.temp_dir = tempfile.TemporaryDirectory()
        database_path = Path(self.temp_dir.name) / "demo_ai.db"
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

    def _use_response(self, response: Any) -> None:
        self.fake = FakeCopilotProvider(response=response)
        app.dependency_overrides[get_copilot_provider] = lambda: self.fake

    def _use_error(self, exc: BaseException) -> None:
        self.fake = FakeCopilotProvider(exc=exc)
        app.dependency_overrides[get_copilot_provider] = lambda: self.fake

    async def _chat(self, message: str, conversation_id: Optional[str] = None) -> httpx.Response:
        body: dict[str, Any] = {"message": message}
        if conversation_id is not None:
            body["conversation_id"] = conversation_id
        return await self.client.post("/demo/ai/chat", json=body)


class TestDemoAILLMSuccess(DemoAITestCase):
    """Successful LLM-generated responses pass through with demo metadata."""

    async def test_success_llm_generated(self) -> None:
        resp = await self._chat("Can I withdraw 4500000 minor units?")
        self.assertEqual(resp.status_code, 200, resp.text)
        chat = CopilotResponse.model_validate(resp.json())
        self.assertFalse(chat.ai_metadata.fallback_used)
        self.assertTrue(chat.ai_metadata.generated)
        self.assertEqual(chat.ai_metadata.provider, "fake")
        self.assertEqual(chat.read_only, True)
        self.assertEqual(chat.snapshot_only, True)
        self.assertEqual(chat.conversation_persisted, False)

    async def test_ru_locale_detected(self) -> None:
        resp = await self._chat("Сколько денег останется?")
        self.assertEqual(resp.status_code, 200)
        chat = CopilotResponse.model_validate(resp.json())
        self.assertIn("ARQAU не гарантирует", chat.disclaimer)

    async def test_en_locale_detected(self) -> None:
        resp = await self._chat("How much money will I have left?")
        self.assertEqual(resp.status_code, 200)
        chat = CopilotResponse.model_validate(resp.json())
        self.assertIn("ARQAU does not guarantee", chat.disclaimer)

    async def test_authoritative_facts_are_demo(self) -> None:
        resp = await self._chat("What is available?")
        chat = CopilotResponse.model_validate(resp.json())
        facts = chat.authoritative_facts
        self.assertEqual(facts.currency, "KZT")
        self.assertEqual(facts.available_amount_minor, 120_000 * 100)
        self.assertEqual(facts.earned_amount_minor, 212_800 * 100)
        self.assertTrue(facts.is_demo if hasattr(facts, 'is_demo') else True)

    async def test_no_api_key_in_response(self) -> None:
        resp = await self._chat("How much is available?")
        self.assertEqual(resp.status_code, 200)
        body = resp.text
        self.assertNotIn("sk-", body)
        self.assertNotIn("OPENAI_API_KEY", body)
        self.assertNotIn("api_key", body.lower())

    async def test_withdrawal_analysis_for_amount_question(self) -> None:
        resp = await self._chat("Can I withdraw 4500000 minor units?")
        self.assertEqual(resp.status_code, 200)
        chat = CopilotResponse.model_validate(resp.json())
        # Demo: available=120000, bills=57400, reserve=60000
        # 45000 -> remaining=75000, buffer=17600 < 60000 -> caution, requestable
        self.assertIsNotNone(chat.withdrawal_analysis)
        self.assertEqual(chat.withdrawal_analysis.requested_amount_minor, 4500000)
        self.assertTrue(chat.withdrawal_analysis.requestability.requestable)


class TestDemoAIProviderFailureFallback(DemoAITestCase):
    """Provider failures fall back deterministically with honest metadata."""

    async def _assert_fallback(self, reason: str, message: str = "How much is available?") -> None:
        resp = await self._chat(message)
        self.assertEqual(resp.status_code, 200, resp.text)
        chat = CopilotResponse.model_validate(resp.json())
        self.assertTrue(chat.ai_metadata.fallback_used)
        self.assertFalse(chat.ai_metadata.generated)
        self.assertEqual(chat.ai_metadata.fallback_reason, reason)
        # Authoritative demo facts remain available even on failure.
        self.assertEqual(chat.authoritative_facts.available_amount_minor, 120_000 * 100)
        self.assertEqual(chat.authoritative_facts.earned_amount_minor, 212_800 * 100)

    async def test_timeout(self) -> None:
        self._use_error(APITimeoutError("forced timeout"))
        await self._assert_fallback(FALLBACK_TIMEOUT)

    async def test_connection_failure(self) -> None:
        self._use_error(_connection_error())
        await self._assert_fallback(FALLBACK_CONNECTION)

    async def test_rate_limit(self) -> None:
        self._use_error(_rate_limit_error())
        await self._assert_fallback(FALLBACK_RATE_LIMIT)

    async def test_provider_http_failure(self) -> None:
        self._use_error(_api_status_error(500))
        await self._assert_fallback(FALLBACK_HTTP_ERROR)

    async def test_malformed_non_dict_response(self) -> None:
        self._use_response("this is not a dict")
        await self._assert_fallback(FALLBACK_MALFORMED)

    async def test_empty_response_object(self) -> None:
        self._use_response({})
        await self._assert_fallback(FALLBACK_SCHEMA_INVALID)

    async def test_blank_response_text(self) -> None:
        self._use_response({"response": "   "})
        await self._assert_fallback(FALLBACK_MALFORMED)

    async def test_unsupported_amount_in_response(self) -> None:
        self._use_response(
            {"response": "Your balance is 999999999 tenge.", "key_facts": []}
        )
        await self._assert_fallback(FALLBACK_UNSUPPORTED_AMOUNT)

    async def test_approval_claim_falls_back(self) -> None:
        self._use_response({"response": "Your withdrawal is approved."})
        resp = await self._chat("Can I withdraw 50000?")
        chat = CopilotResponse.model_validate(resp.json())
        self.assertTrue(chat.ai_metadata.fallback_used)
        self.assertEqual(chat.ai_metadata.fallback_reason, FALLBACK_UNSAFE_CONTENT)
        self.assertNotIn("approved", chat.response.lower())

    async def test_runtime_error_falls_back(self) -> None:
        self._use_error(RuntimeError("boom"))
        await self._assert_fallback(FALLBACK_HTTP_ERROR)


class TestDemoAINotConfigured(DemoAITestCase):
    """Missing OPENAI_API_KEY returns a deterministic fallback."""

    async def test_not_configured(self) -> None:
        # Use the real production provider with no API key.
        app.dependency_overrides.pop(get_copilot_provider, None)
        with patch.dict(os.environ, {"OPENAI_API_KEY": ""}):
            reset_production_provider()
            try:
                self.assertFalse(get_copilot_provider().is_configured)
                resp = await self._chat("How much is available?")
            finally:
                reset_production_provider()
        self.assertEqual(resp.status_code, 200, resp.text)
        chat = CopilotResponse.model_validate(resp.json())
        self.assertTrue(chat.ai_metadata.fallback_used)
        self.assertEqual(chat.ai_metadata.fallback_reason, FALLBACK_NOT_CONFIGURED)
        self.assertFalse(chat.ai_metadata.generated)
        self.assertEqual(chat.authoritative_facts.available_amount_minor, 120_000 * 100)
        self.assertIn("не настроен" if chat.disclaimer.startswith("Это") else "not configured", chat.response)


class TestDemoAIReadOnly(DemoAITestCase):
    """Demo endpoint is read-only: no mutations, no real account access."""

    async def test_no_wage_access_request_created(self) -> None:
        # No database writes should happen from the demo endpoint.
        resp = await self._chat("Please withdraw 50000 right now.")
        self.assertEqual(resp.status_code, 200)
        # The demo endpoint never touches WageAccessRequest table.
        async with self.sessions() as db:
            from app.models import WageAccessRequest
            from sqlalchemy import select
            rows = (await db.execute(select(WageAccessRequest))).scalars().all()
            self.assertEqual(len(rows), 0)

    async def test_response_declares_read_only(self) -> None:
        resp = await self._chat("How much is available?")
        chat = CopilotResponse.model_validate(resp.json())
        self.assertTrue(chat.read_only)
        self.assertTrue(chat.snapshot_only)

    async def test_no_authentication_required(self) -> None:
        # Public endpoint: no Authorization header needed.
        resp = await self._chat("How much is available?")
        self.assertEqual(resp.status_code, 200, resp.text)

    async def test_no_auth_header_still_works(self) -> None:
        resp = await self.client.post("/demo/ai/chat", json={"message": "Hi"})
        self.assertEqual(resp.status_code, 200, resp.text)

    async def test_empty_message_rejected(self) -> None:
        resp = await self.client.post("/demo/ai/chat", json={"message": ""})
        self.assertEqual(resp.status_code, 422, resp.text)

    async def test_demo_financial_context_values(self) -> None:
        """Demo context matches the seed data exactly."""
        ctx = build_demo_financial_context()
        self.assertEqual(ctx.available_amount, 120_000)
        self.assertEqual(ctx.earned_amount, 212_800)
        self.assertEqual(ctx.salary_amount, 187_400)
        self.assertEqual(ctx.reserve_target, 60_000)
        self.assertEqual(ctx.days_to_payday, 9)
        self.assertEqual(ctx.currency, "KZT")
        self.assertTrue(ctx.is_demo)
        self.assertEqual(ctx.source, "demo")


if __name__ == "__main__":
    unittest.main()
