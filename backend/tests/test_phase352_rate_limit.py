"""Phase 3.5.2A RateLimiter core + total ceiling + provider integration tests.

Uses unittest.IsolatedAsyncioTestCase — no pytest-asyncio dependency.
"""
import asyncio
import os
import tempfile
import unittest
from datetime import date, datetime
from pathlib import Path
from fastapi import HTTPException

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.database import Base, configure_database, create_database
from app.core.rate_limit import (
    RateLimiter,
    enforce_total_ceiling,
    get_total_limiter,
    get_provider_limiter,
)
from app.core.auth_rate_limit import _reset_all_limiters
from app.core.security import get_password_hash
from app.database import get_db
from app.main import app
from app.models import (
    Budget,
    EwaPolicy,
    Employee,
    Employer,
    Employment,
    Goal,
    SalaryProfile,
    Transaction,
    User,
    WageAccessRequest,
)
from app.schemas.ai_copilot import (
    AuthoritativeCopilotFacts,
    CopilotAnswer,
    CopilotContent,
    CopilotFact,
    CopilotMetadata,
    CopilotResponse,
    SpendingCategoryFact,
)
from app.schemas.ai_decision import (
    DecisionContent,
    WithdrawalDecisionResponse,
)
from app.schemas.financial_context import (
    FinancialContext,
    WithdrawalAnalysis,
    WithdrawalAnalysisRequest,
)
from app.services.ai_copilot import (
    FakeCopilotProvider,
    build_authoritative_facts,
    build_sanitized_input,
    generate_copilot_answer,
    get_copilot_provider,
)
from app.services.ai_decision import (
    FakeDecisionProvider,
    build_sanitized_input as build_decision_sanitized_input,
    generate_decision,
    get_decision_provider,
    make_withdrawal_decision,
)
from app.services.financial_context_service import (
    analyze_withdrawal_from_context,
    build_financial_context,
)

os.environ.setdefault("APP_ENV", "testing")
os.environ.setdefault("SECRET_KEY", "test-secret")
os.environ.setdefault("OPENAI_API_KEY", "")
os.environ.setdefault("OPENAI_MODEL", "gpt-4o-mini")

CALC_DATE = date(2026, 2, 15)

DEFAULT_POLICY = dict(
    enabled=True,
    max_access_percentage=50,
    max_withdrawals_per_period=3,
    minimum_tenure_days=7,
    minimum_remaining_salary_minor=1000,
    minimum_withdrawal_minor=2000,
    maximum_withdrawal_minor=50000,
)

FAKE_COPILOT_CONTENT = {
    "response": "Your earned amount is 1000000 minor units and available is 500000.",
    "key_facts": [
        {"code": "earned_amount", "text": "Salary earned this pay period: 1000000 minor units."},
        {"code": "available_amount", "text": "Available EWA capacity: 500000 minor units."},
    ],
    "considerations": [],
    "options": [
        {"code": "opt_continue", "text": "Proceed with the standard request flow when ready."},
    ],
    "data_limitations": [],
    "disclaimer": "This is illustrative guidance, not financial advice. ARQAU does not guarantee any specific financial outcome.",
}

FAKE_DECISION_CONTENT = {
    "summary": "The requested amount is within the deterministic EWA limits.",
    "status_explanation": "The withdrawal amount is covered by the currently available and max requestable capacity.",
    "key_facts": [
        {"code": "available_amount", "text": "Available capacity is sufficient."},
        {"code": "max_requestable", "text": "Amount does not exceed the maximum."},
    ],
    "considerations": [
        {"code": "no_blocks", "text": "No deterministic blocking conditions apply."}
    ],
    "options": [
        {"code": "opt_continue", "text": "Proceed with the standard request flow when ready."},
        {"code": "opt_review_amount", "text": "Review the requested amount if desired."},
    ],
    "data_limitations": [],
    "disclaimer": "This is illustrative guidance, not financial advice. ARQAU does not guarantee any specific financial outcome.",
}


class FakeClock:
    def __init__(self, start: float = 0.0):
        self._now = start

    def __call__(self) -> float:
        return self._now

    def advance(self, seconds: float) -> None:
        self._now += seconds


class TestProviderLimiter(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.clock = FakeClock()
        self.limiter = RateLimiter(max_calls=20, window_seconds=3600.0, clock=self.clock)

    async def test_allows_exactly_20_acquisitions(self) -> None:
        for _ in range(20):
            self.assertTrue(await self.limiter.try_acquire("user1"))

    async def test_21st_acquisition_blocked(self) -> None:
        for _ in range(20):
            await self.limiter.try_acquire("user1")
        self.assertFalse(await self.limiter.try_acquire("user1"))

    async def test_separate_users_independent_budgets(self) -> None:
        for _ in range(20):
            await self.limiter.try_acquire("user1")
        self.assertTrue(await self.limiter.try_acquire("user2"))

    async def test_window_resets_with_fake_clock(self) -> None:
        for _ in range(20):
            await self.limiter.try_acquire("user1")
        self.assertFalse(await self.limiter.try_acquire("user1"))

        self.clock.advance(3600.0)
        self.assertTrue(await self.limiter.try_acquire("user1"))

    async def test_concurrent_acquisitions_not_exceed_limit(self) -> None:
        async def acquire() -> bool:
            return await self.limiter.try_acquire("user1")

        results = await asyncio.gather(*[acquire() for _ in range(30)])
        allowed = sum(results)
        self.assertEqual(allowed, 20)

    async def test_expired_buckets_lazily_cleaned(self) -> None:
        # Fill buckets well past cleanup threshold (1000)
        for i in range(1100):
            await self.limiter.try_acquire(f"user{i}")
        self.assertEqual(len(self.limiter._buckets), 1100)

        # Advance clock so first 1000 are expired
        self.clock.advance(3600.0)

        # Trigger cleanup by adding one more bucket
        await self.limiter.try_acquire("new_user")

        # Expired buckets should be gone
        self.assertNotIn("user0", self.limiter._buckets)
        self.assertNotIn("user500", self.limiter._buckets)
        self.assertIn("new_user", self.limiter._buckets)

    async def test_remaining_correct(self) -> None:
        self.assertEqual(self.limiter.remaining("user1"), 20)
        await self.limiter.try_acquire("user1")
        self.assertEqual(self.limiter.remaining("user1"), 19)
        for _ in range(18):
            await self.limiter.try_acquire("user1")
        self.assertEqual(self.limiter.remaining("user1"), 1)
        await self.limiter.try_acquire("user1")
        self.assertEqual(self.limiter.remaining("user1"), 0)

    async def test_retry_after_seconds_correct(self) -> None:
        await self.limiter.try_acquire("user1")
        retry = self.limiter.retry_after_seconds("user1")
        self.assertEqual(retry, 3600.0)

        self.clock.advance(1800.0)
        retry = self.limiter.retry_after_seconds("user1")
        self.assertEqual(retry, 1800.0)

        self.clock.advance(1800.0)
        retry = self.limiter.retry_after_seconds("user1")
        self.assertEqual(retry, 0.0)

    def test_invalid_max_calls_rejected(self) -> None:
        with self.assertRaises(ValueError) as cm:
            RateLimiter(max_calls=0, window_seconds=60.0)
        self.assertIn("max_calls must be positive", str(cm.exception))

        with self.assertRaises(ValueError) as cm:
            RateLimiter(max_calls=-1, window_seconds=60.0)
        self.assertIn("max_calls must be positive", str(cm.exception))

    def test_invalid_window_seconds_rejected(self) -> None:
        with self.assertRaises(ValueError) as cm:
            RateLimiter(max_calls=10, window_seconds=0)
        self.assertIn("window_seconds must be positive", str(cm.exception))

        with self.assertRaises(ValueError) as cm:
            RateLimiter(max_calls=10, window_seconds=-1)
        self.assertIn("window_seconds must be positive", str(cm.exception))


class TestTotalCeiling(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.clock = FakeClock()
        # Use the module-level singleton that enforce_total_ceiling() uses
        self.total_limiter = get_total_limiter()
        self.total_limiter._clock = self.clock
        self.total_limiter.reset()

    async def test_allows_exactly_120_acquisitions(self) -> None:
        for _ in range(120):
            self.assertTrue(await self.total_limiter.try_acquire("user1"))

    async def test_121st_through_enforce_raises_429(self) -> None:
        for _ in range(120):
            await self.total_limiter.try_acquire("user1")
        with self.assertRaises(HTTPException) as cm:
            await enforce_total_ceiling("user1")
        self.assertEqual(cm.exception.status_code, 429)

    async def test_429_contains_positive_integer_retry_after(self) -> None:
        for _ in range(120):
            await self.total_limiter.try_acquire("user1")
        with self.assertRaises(HTTPException) as cm:
            await enforce_total_ceiling("user1")
        retry_after = cm.exception.headers.get("Retry-After")
        self.assertIsNotNone(retry_after)
        self.assertGreater(int(retry_after), 0)


class _ProviderIntegrationBase(unittest.IsolatedAsyncioTestCase):
    """Shared test infrastructure for provider integration tests."""

    async def asyncSetUp(self) -> None:
        _reset_all_limiters()
        self.temp_dir = tempfile.TemporaryDirectory()
        database_path = Path(self.temp_dir.name) / "phase352.db"
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

        # Set up user with financial context
        async with self.sessions() as db:
            employer = Employer(id="emp-352", legal_name="Co 352")
            db.add(employer)
            await db.commit()
            policy = EwaPolicy(
                id="policy-352", employer_id=employer.id, **DEFAULT_POLICY
            )
            db.add(policy)
            # Create user
            user = User(id="user-352", email="test352@example.com", name="Test User", hashed_password=get_password_hash("password123"))
            db.add(user)
            await db.commit()
            employee = Employee(id="emp-352-emp", user_id=user.id, status="active")
            db.add(employee)
            employment = Employment(
                id="emp-352-employment",
                employee_id=employee.id,
                employer_id=employer.id,
                status="active",
                start_date=datetime(2026, 1, 1),
                eligible_from=datetime(2026, 1, 1),
            )
            db.add(employment)
            salary = SalaryProfile(
                id="sal-352",
                employment_id=employment.id,
                currency="USD",
                monthly_salary_amount_minor=1000000,
                pay_schedule="monthly",
                effective_from=datetime(2026, 1, 1),
                status="active",
            )
            db.add(salary)
            await db.commit()
            self.user_id = user.id

        # Set up fake clock and provider limiter
        self.clock = FakeClock()
        self.provider_limiter = get_provider_limiter()
        self.provider_limiter._clock = self.clock
        self.provider_limiter.reset()

        # Also reset total limiter to avoid interference from other tests
        self.total_limiter = get_total_limiter()
        self.total_limiter._clock = self.clock
        self.total_limiter.reset()

        self.client = httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://testserver",
        )

        # Login to get token
        resp = await self.client.post(
            "/auth/login",
            json={"email": "test352@example.com", "password": "password123"},
        )
        self.assertEqual(resp.status_code, 200, resp.text)
        self.token = resp.json()["access_token"]

    async def asyncTearDown(self) -> None:
        await self.client.aclose()
        app.dependency_overrides.clear()
        await self.engine.dispose()
        self.temp_dir.cleanup()
        if self.original_url:
            await configure_database(self.original_url)


class TestCopilotProviderIntegration(_ProviderIntegrationBase):
    """Tier 1 provider-call budget integration with Copilot."""

    async def test_attempts_1_to_20_invoke_provider(self) -> None:
        fake = FakeCopilotProvider(response=FAKE_COPILOT_CONTENT)
        app.dependency_overrides[get_copilot_provider] = lambda: fake

        for i in range(1, 21):
            resp = await self.client.post(
                "/ai/chat",
                headers={"Authorization": f"Bearer {self.token}"},
                json={"message": "How much have I earned?"},
            )
            self.assertEqual(resp.status_code, 200, resp.text)

        self.assertEqual(fake.call_count, 20)

    async def test_attempt_21_blocked_no_provider_call(self) -> None:
        fake = FakeCopilotProvider(response=FAKE_COPILOT_CONTENT)
        app.dependency_overrides[get_copilot_provider] = lambda: fake

        for _ in range(20):
            await self.client.post(
                "/ai/chat",
                headers={"Authorization": f"Bearer {self.token}"},
                json={"message": "How much have I earned?"},
            )

        resp = await self.client.post(
            "/ai/chat",
            headers={"Authorization": f"Bearer {self.token}"},
            json={"message": "How much have I earned?"},
        )
        self.assertEqual(resp.status_code, 200, resp.text)
        self.assertEqual(fake.call_count, 20)

    async def test_blocked_result_has_fallback_metadata(self) -> None:
        fake = FakeCopilotProvider(response=FAKE_COPILOT_CONTENT)
        app.dependency_overrides[get_copilot_provider] = lambda: fake

        for _ in range(20):
            await self.client.post(
                "/ai/chat",
                headers={"Authorization": f"Bearer {self.token}"},
                json={"message": "How much have I earned?"},
            )

        resp = await self.client.post(
            "/ai/chat",
            headers={"Authorization": f"Bearer {self.token}"},
            json={"message": "How much have I earned?"},
        )
        data = resp.json()
        self.assertTrue(data["ai_metadata"]["fallback_used"])
        self.assertEqual(data["ai_metadata"]["fallback_reason"], "local_rate_limit")
        self.assertFalse(data["ai_metadata"]["generated"])

    async def test_fallback_is_deterministic(self) -> None:
        fake = FakeCopilotProvider(response=FAKE_COPILOT_CONTENT)
        app.dependency_overrides[get_copilot_provider] = lambda: fake

        for _ in range(20):
            await self.client.post(
                "/ai/chat",
                headers={"Authorization": f"Bearer {self.token}"},
                json={"message": "How much have I earned?"},
            )

        resp1 = await self.client.post(
            "/ai/chat",
            headers={"Authorization": f"Bearer {self.token}"},
            json={"message": "How much have I earned?"},
        )
        resp2 = await self.client.post(
            "/ai/chat",
            headers={"Authorization": f"Bearer {self.token}"},
            json={"message": "How much have I earned?"},
        )

        # Both blocked responses should have identical deterministic fallback
        self.assertEqual(resp1.json()["response"], resp2.json()["response"])
        self.assertEqual(resp1.json()["key_facts"], resp2.json()["key_facts"])
        self.assertEqual(resp1.json()["data_limitations"], resp2.json()["data_limitations"])

    async def test_fallback_uses_server_owned_financial_values(self) -> None:
        fake = FakeCopilotProvider(response=FAKE_COPILOT_CONTENT)
        app.dependency_overrides[get_copilot_provider] = lambda: fake

        for _ in range(20):
            await self.client.post(
                "/ai/chat",
                headers={"Authorization": f"Bearer {self.token}"},
                json={"message": "How much have I earned?"},
            )

        resp = await self.client.post(
            "/ai/chat",
            headers={"Authorization": f"Bearer {self.token}"},
            json={"message": "How much have I earned?"},
        )
        data = resp.json()

        # Authoritative facts should be from server, not invented
        self.assertIn("authoritative_facts", data)
        facts = data["authoritative_facts"]
        # Values should be present and server-owned (not None)
        self.assertIsNotNone(facts.get("earned_amount_minor"))
        self.assertEqual(facts["currency"], "USD")
        self.assertIsNotNone(facts.get("available_amount_minor"))
        self.assertIsNotNone(facts.get("max_requestable_amount_minor"))

    async def test_fallback_does_not_invent_withdrawal_recommendation(self) -> None:
        fake = FakeCopilotProvider(response=FAKE_COPILOT_CONTENT)
        app.dependency_overrides[get_copilot_provider] = lambda: fake

        for _ in range(20):
            await self.client.post(
                "/ai/chat",
                headers={"Authorization": f"Bearer {self.token}"},
                json={"message": "How much have I earned?"},
            )

        resp = await self.client.post(
            "/ai/chat",
            headers={"Authorization": f"Bearer {self.token}"},
            json={"message": "How much have I earned?"},
        )
        response_text = resp.json()["response"]

        # Should NOT contain affirmative withdrawal recommendations
        self.assertNotIn("should withdraw", response_text.lower())
        self.assertNotIn("withdraw all", response_text.lower())
        self.assertNotIn("safe to withdraw", response_text.lower())
        # The phrase "not a recommendation" is expected and correct

    async def test_unconfigured_provider_does_not_consume_budget(self) -> None:
        # Provider with no API key -> is_configured == False
        class UnconfiguredCopilotProvider(FakeCopilotProvider):
            @property
            def is_configured(self) -> bool:
                return False

        fake = UnconfiguredCopilotProvider()
        app.dependency_overrides[get_copilot_provider] = lambda: fake

        # 5 calls to unconfigured provider
        for _ in range(5):
            resp = await self.client.post(
                "/ai/chat",
                headers={"Authorization": f"Bearer {self.token}"},
                json={"message": "How much have I earned?"},
            )
            self.assertEqual(resp.status_code, 200, resp.text)

        # Budget should not be consumed - we can still make 20 calls to a configured provider
        fake2 = FakeCopilotProvider(response=FAKE_COPILOT_CONTENT)
        app.dependency_overrides[get_copilot_provider] = lambda: fake2

        for _ in range(20):
            resp = await self.client.post(
                "/ai/chat",
                headers={"Authorization": f"Bearer {self.token}"},
                json={"message": "How much have I earned?"},
            )
            self.assertEqual(resp.status_code, 200, resp.text)

        # 21st call to configured provider should be blocked
        resp = await self.client.post(
            "/ai/chat",
            headers={"Authorization": f"Bearer {self.token}"},
            json={"message": "How much have I earned?"},
        )
        self.assertTrue(resp.json()["ai_metadata"]["fallback_used"])


class TestDecisionProviderIntegration(_ProviderIntegrationBase):
    """Tier 1 provider-call budget integration with structured decision."""

    async def test_attempts_1_to_20_invoke_provider(self) -> None:
        fake = FakeDecisionProvider(response=FAKE_DECISION_CONTENT)
        app.dependency_overrides[get_decision_provider] = lambda: fake

        for i in range(1, 21):
            resp = await self.client.post(
                "/financial/withdrawal-decision",
                headers={"Authorization": f"Bearer {self.token}"},
                json={"amount_minor": 10000},
            )
            self.assertEqual(resp.status_code, 200, resp.text)

        self.assertEqual(fake.call_count, 20)

    async def test_attempt_21_blocked_no_provider_call(self) -> None:
        fake = FakeDecisionProvider(response=FAKE_DECISION_CONTENT)
        app.dependency_overrides[get_decision_provider] = lambda: fake

        for _ in range(20):
            await self.client.post(
                "/financial/withdrawal-decision",
                headers={"Authorization": f"Bearer {self.token}"},
                json={"amount_minor": 10000},
            )

        resp = await self.client.post(
            "/financial/withdrawal-decision",
            headers={"Authorization": f"Bearer {self.token}"},
            json={"amount_minor": 10000},
        )
        self.assertEqual(resp.status_code, 200, resp.text)
        self.assertEqual(fake.call_count, 20)

    async def test_blocked_returns_deterministic_fallback(self) -> None:
        fake = FakeDecisionProvider(response=FAKE_DECISION_CONTENT)
        app.dependency_overrides[get_decision_provider] = lambda: fake

        for _ in range(20):
            await self.client.post(
                "/financial/withdrawal-decision",
                headers={"Authorization": f"Bearer {self.token}"},
                json={"amount_minor": 10000},
            )

        resp = await self.client.post(
            "/financial/withdrawal-decision",
            headers={"Authorization": f"Bearer {self.token}"},
            json={"amount_minor": 10000},
        )
        data = resp.json()
        self.assertTrue(data["decision"]["ai_metadata"]["fallback_used"])
        self.assertFalse(data["decision"]["ai_metadata"]["generated"])

    async def test_unconfigured_provider_does_not_consume_budget(self) -> None:
        # Provider with no API key -> is_configured == False
        class UnconfiguredDecisionProvider(FakeDecisionProvider):
            @property
            def is_configured(self) -> bool:
                return False

        fake = UnconfiguredDecisionProvider()
        app.dependency_overrides[get_decision_provider] = lambda: fake

        # 5 calls to unconfigured provider
        for _ in range(5):
            resp = await self.client.post(
                "/financial/withdrawal-decision",
                headers={"Authorization": f"Bearer {self.token}"},
                json={"amount_minor": 10000},
            )
            self.assertEqual(resp.status_code, 200, resp.text)

        # Budget should not be consumed - we can still make 20 calls to a configured provider
        fake2 = FakeDecisionProvider(response=FAKE_DECISION_CONTENT)
        app.dependency_overrides[get_decision_provider] = lambda: fake2

        for _ in range(20):
            resp = await self.client.post(
                "/financial/withdrawal-decision",
                headers={"Authorization": f"Bearer {self.token}"},
                json={"amount_minor": 10000},
            )
            self.assertEqual(resp.status_code, 200, resp.text)

        # 21st call to configured provider should be blocked
        resp = await self.client.post(
            "/financial/withdrawal-decision",
            headers={"Authorization": f"Bearer {self.token}"},
            json={"amount_minor": 10000},
        )
        self.assertTrue(resp.json()["decision"]["ai_metadata"]["fallback_used"])


class TestTotalCeilingRouteIntegration(_ProviderIntegrationBase):
    """Route-level total AI request ceiling (Tier 2) integration tests."""

    async def asyncSetUp(self) -> None:
        await super().asyncSetUp()
        # Override the module-level provider limiter to allow 120 calls
        # (match total ceiling) so provider budget doesn't interfere
        provider_limiter = get_provider_limiter()
        provider_limiter._max_calls = 120
        provider_limiter._window_seconds = 60.0
        provider_limiter._clock = self.clock
        provider_limiter.reset()

    async def test_ai_chat_requests_1_to_120_allowed(self) -> None:
        # Mock provider to avoid real AI calls
        fake = FakeCopilotProvider(response=FAKE_COPILOT_CONTENT)
        app.dependency_overrides[get_copilot_provider] = lambda: fake

        for i in range(1, 121):
            resp = await self.client.post(
                "/ai/chat",
                headers={"Authorization": f"Bearer {self.token}"},
                json={"message": "How much have I earned?"},
            )
            self.assertEqual(resp.status_code, 200, f"Request {i} failed: {resp.text}")

        self.assertEqual(fake.call_count, 120)

    async def test_ai_chat_request_121_blocked_429(self) -> None:
        fake = FakeCopilotProvider(response=FAKE_COPILOT_CONTENT)
        app.dependency_overrides[get_copilot_provider] = lambda: fake

        for _ in range(120):
            await self.client.post(
                "/ai/chat",
                headers={"Authorization": f"Bearer {self.token}"},
                json={"message": "How much have I earned?"},
            )

        resp = await self.client.post(
            "/ai/chat",
            headers={"Authorization": f"Bearer {self.token}"},
            json={"message": "How much have I earned?"},
        )
        self.assertEqual(resp.status_code, 429)
        self.assertEqual(fake.call_count, 120)  # Provider not called for 121st

    async def test_ai_chat_429_has_retry_after_integer_positive(self) -> None:
        fake = FakeCopilotProvider(response=FAKE_COPILOT_CONTENT)
        app.dependency_overrides[get_copilot_provider] = lambda: fake

        for _ in range(120):
            await self.client.post(
                "/ai/chat",
                headers={"Authorization": f"Bearer {self.token}"},
                json={"message": "How much have I earned?"},
            )

        resp = await self.client.post(
            "/ai/chat",
            headers={"Authorization": f"Bearer {self.token}"},
            json={"message": "How much have I earned?"},
        )
        self.assertEqual(resp.status_code, 429)
        retry_after = resp.headers.get("Retry-After")
        self.assertIsNotNone(retry_after)
        self.assertGreater(int(retry_after), 0)

    async def test_ai_chat_separate_users_independent_total_budget(self) -> None:
        # Create second user
        async with self.sessions() as db:
            user2 = User(id="user-352b", email="test352b@example.com", name="Test User B", hashed_password=get_password_hash("password123"))
            db.add(user2)
            await db.commit()
            employee = Employee(id="emp-352b-emp", user_id=user2.id, status="active")
            db.add(employee)
            employer = await db.get(Employer, "emp-352")
            employment = Employment(
                id="emp-352b-employment",
                employee_id=employee.id,
                employer_id=employer.id,
                status="active",
                start_date=datetime(2026, 1, 1),
                eligible_from=datetime(2026, 1, 1),
            )
            db.add(employment)
            salary = SalaryProfile(
                id="sal-352b",
                employment_id=employment.id,
                currency="USD",
                monthly_salary_amount_minor=1000000,
                pay_schedule="monthly",
                effective_from=datetime(2026, 1, 1),
                status="active",
            )
            db.add(salary)
            await db.commit()
            self.user_id_2 = user2.id

        # Login as second user
        resp = await self.client.post(
            "/auth/login",
            json={"email": "test352b@example.com", "password": "password123"},
        )
        self.assertEqual(resp.status_code, 200, resp.text)
        token2 = resp.json()["access_token"]

        fake = FakeCopilotProvider(response=FAKE_COPILOT_CONTENT)
        app.dependency_overrides[get_copilot_provider] = lambda: fake

        # Exhaust user1's budget (120 requests)
        for _ in range(120):
            await self.client.post(
                "/ai/chat",
                headers={"Authorization": f"Bearer {self.token}"},
                json={"message": "How much have I earned?"},
            )

        # User2 should still have full budget
        resp = await self.client.post(
            "/ai/chat",
            headers={"Authorization": f"Bearer {token2}"},
            json={"message": "How much have I earned?"},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(fake.call_count, 121)  # 120 for user1 + 1 for user2

    # POST /ai/analyze-withdrawal route tests
    async def test_ai_analyze_withdrawal_requests_1_to_120_allowed(self) -> None:
        # Mock provider to avoid real AI calls
        fake = FakeDecisionProvider(response=FAKE_DECISION_CONTENT)
        app.dependency_overrides[get_decision_provider] = lambda: fake

        for i in range(1, 121):
            resp = await self.client.post(
                "/ai/analyze-withdrawal",
                headers={"Authorization": f"Bearer {self.token}"},
                json={"withdrawal_amount": 5000},
            )
            self.assertEqual(resp.status_code, 200, f"Request {i} failed: {resp.text}")

        self.assertEqual(fake.call_count, 120)

    async def test_ai_analyze_withdrawal_request_121_blocked_429(self) -> None:
        fake = FakeDecisionProvider(response=FAKE_DECISION_CONTENT)
        app.dependency_overrides[get_decision_provider] = lambda: fake

        for _ in range(120):
            await self.client.post(
                "/ai/analyze-withdrawal",
                headers={"Authorization": f"Bearer {self.token}"},
                json={"withdrawal_amount": 5000},
            )

        resp = await self.client.post(
            "/ai/analyze-withdrawal",
            headers={"Authorization": f"Bearer {self.token}"},
            json={"withdrawal_amount": 5000},
        )
        self.assertEqual(resp.status_code, 429)
        self.assertEqual(fake.call_count, 120)  # Provider not called for 121st

    async def test_ai_analyze_withdrawal_429_has_retry_after_integer_positive(self) -> None:
        fake = FakeDecisionProvider(response=FAKE_DECISION_CONTENT)
        app.dependency_overrides[get_decision_provider] = lambda: fake

        for _ in range(120):
            await self.client.post(
                "/ai/analyze-withdrawal",
                headers={"Authorization": f"Bearer {self.token}"},
                json={"withdrawal_amount": 5000},
            )

        resp = await self.client.post(
            "/ai/analyze-withdrawal",
            headers={"Authorization": f"Bearer {self.token}"},
            json={"withdrawal_amount": 5000},
        )
        self.assertEqual(resp.status_code, 429)
        retry_after = resp.headers.get("Retry-After")
        self.assertIsNotNone(retry_after)
        self.assertGreater(int(retry_after), 0)

    async def test_ai_analyze_withdrawal_separate_users_independent_total_budget(self) -> None:
        # Create second user
        async with self.sessions() as db:
            user2 = User(id="user-352c", email="test352c@example.com", name="Test User C", hashed_password=get_password_hash("password123"))
            db.add(user2)
            await db.commit()
            employee = Employee(id="emp-352c-emp", user_id=user2.id, status="active")
            db.add(employee)
            employer = await db.get(Employer, "emp-352")
            employment = Employment(
                id="emp-352c-employment",
                employee_id=employee.id,
                employer_id=employer.id,
                status="active",
                start_date=datetime(2026, 1, 1),
                eligible_from=datetime(2026, 1, 1),
            )
            db.add(employment)
            salary = SalaryProfile(
                id="sal-352c",
                employment_id=employment.id,
                currency="USD",
                monthly_salary_amount_minor=1000000,
                pay_schedule="monthly",
                effective_from=datetime(2026, 1, 1),
                status="active",
            )
            db.add(salary)
            await db.commit()
            self.user_id_3 = user2.id

        # Login as second user
        resp = await self.client.post(
            "/auth/login",
            json={"email": "test352c@example.com", "password": "password123"},
        )
        self.assertEqual(resp.status_code, 200, resp.text)
        token2 = resp.json()["access_token"]

        fake = FakeDecisionProvider(response=FAKE_DECISION_CONTENT)
        app.dependency_overrides[get_decision_provider] = lambda: fake

        # Exhaust user1's budget (120 requests)
        for _ in range(120):
            await self.client.post(
                "/ai/analyze-withdrawal",
                headers={"Authorization": f"Bearer {self.token}"},
                json={"withdrawal_amount": 5000},
            )

        # User2 should still have full budget
        resp = await self.client.post(
            "/ai/analyze-withdrawal",
            headers={"Authorization": f"Bearer {token2}"},
            json={"withdrawal_amount": 5000},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(fake.call_count, 121)  # 120 for user1 + 1 for user2

    # POST /financial/withdrawal-decision route tests (protected by total ceiling)
    async def test_financial_withdrawal_decision_requests_1_to_120_allowed(self) -> None:
        fake = FakeDecisionProvider(response=FAKE_DECISION_CONTENT)
        app.dependency_overrides[get_decision_provider] = lambda: fake

        for i in range(1, 121):
            resp = await self.client.post(
                "/financial/withdrawal-decision",
                headers={"Authorization": f"Bearer {self.token}"},
                json={"amount_minor": 5000},
            )
            self.assertEqual(resp.status_code, 200, f"Request {i} failed: {resp.text}")

        self.assertEqual(fake.call_count, 120)

    async def test_financial_withdrawal_decision_request_121_blocked_429(self) -> None:
        fake = FakeDecisionProvider(response=FAKE_DECISION_CONTENT)
        app.dependency_overrides[get_decision_provider] = lambda: fake

        for _ in range(120):
            await self.client.post(
                "/financial/withdrawal-decision",
                headers={"Authorization": f"Bearer {self.token}"},
                json={"amount_minor": 5000},
            )

        resp = await self.client.post(
            "/financial/withdrawal-decision",
            headers={"Authorization": f"Bearer {self.token}"},
            json={"amount_minor": 5000},
        )
        self.assertEqual(resp.status_code, 429)
        self.assertEqual(fake.call_count, 120)  # Provider not called for 121st

    async def test_financial_withdrawal_decision_429_has_retry_after_integer_positive(self) -> None:
        fake = FakeDecisionProvider(response=FAKE_DECISION_CONTENT)
        app.dependency_overrides[get_decision_provider] = lambda: fake

        for _ in range(120):
            await self.client.post(
                "/financial/withdrawal-decision",
                headers={"Authorization": f"Bearer {self.token}"},
                json={"amount_minor": 5000},
            )

        resp = await self.client.post(
            "/financial/withdrawal-decision",
            headers={"Authorization": f"Bearer {self.token}"},
            json={"amount_minor": 5000},
        )
        self.assertEqual(resp.status_code, 429)
        retry_after = resp.headers.get("Retry-After")
        self.assertIsNotNone(retry_after)
        self.assertGreater(int(retry_after), 0)

    async def test_financial_withdrawal_decision_separate_users_independent_total_budget(self) -> None:
        # Create second user
        async with self.sessions() as db:
            user2 = User(id="user-352d", email="test352d@example.com", name="Test User D", hashed_password=get_password_hash("password123"))
            db.add(user2)
            await db.commit()
            employee = Employee(id="emp-352d-emp", user_id=user2.id, status="active")
            db.add(employee)
            employer = await db.get(Employer, "emp-352")
            employment = Employment(
                id="emp-352d-employment",
                employee_id=employee.id,
                employer_id=employer.id,
                status="active",
                start_date=datetime(2026, 1, 1),
                eligible_from=datetime(2026, 1, 1),
            )
            db.add(employment)
            salary = SalaryProfile(
                id="sal-352d",
                employment_id=employment.id,
                currency="USD",
                monthly_salary_amount_minor=1000000,
                pay_schedule="monthly",
                effective_from=datetime(2026, 1, 1),
                status="active",
            )
            db.add(salary)
            await db.commit()

        # Login as second user
        resp = await self.client.post(
            "/auth/login",
            json={"email": "test352d@example.com", "password": "password123"},
        )
        self.assertEqual(resp.status_code, 200, resp.text)
        token2 = resp.json()["access_token"]

        fake = FakeDecisionProvider(response=FAKE_DECISION_CONTENT)
        app.dependency_overrides[get_decision_provider] = lambda: fake

        # Exhaust user1's budget (120 requests)
        for _ in range(120):
            await self.client.post(
                "/financial/withdrawal-decision",
                headers={"Authorization": f"Bearer {self.token}"},
                json={"amount_minor": 5000},
            )

        # User2 should still have full budget
        resp = await self.client.post(
            "/financial/withdrawal-decision",
            headers={"Authorization": f"Bearer {token2}"},
            json={"amount_minor": 5000},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(fake.call_count, 121)  # 120 for user1 + 1 for user2

    # Deterministic-only routes: verify they do NOT consume total AI ceiling
    async def test_financial_context_get_does_not_consume_total_ceiling(self) -> None:
        # Establish known total-limiter state: 50 requests used
        total_limiter = get_total_limiter()
        for _ in range(50):
            await total_limiter.try_acquire("test-user-deterministic")

        remaining_before = total_limiter.remaining("test-user-deterministic")

        # Call deterministic route
        resp = await self.client.get(
            "/financial/context",
            headers={"Authorization": f"Bearer {self.token}"},
        )
        self.assertEqual(resp.status_code, 200)

        remaining_after = total_limiter.remaining("test-user-deterministic")
        self.assertEqual(remaining_after, remaining_before)

    async def test_financial_withdrawal_analysis_post_does_not_consume_total_ceiling(self) -> None:
        # Establish known total-limiter state: 50 requests used
        total_limiter = get_total_limiter()
        for _ in range(50):
            await total_limiter.try_acquire("test-user-deterministic2")

        remaining_before = total_limiter.remaining("test-user-deterministic2")

        # Call deterministic route
        resp = await self.client.post(
            "/financial/withdrawal-analysis",
            headers={"Authorization": f"Bearer {self.token}"},
            json={"amount_minor": 5000},
        )
        self.assertEqual(resp.status_code, 200)

        remaining_after = total_limiter.remaining("test-user-deterministic2")
        self.assertEqual(remaining_after, remaining_before)


if __name__ == "__main__":
    unittest.main()