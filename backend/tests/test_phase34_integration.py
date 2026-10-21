"""Phase 3.4 real OpenRouter integration test for the AI copilot.

This test makes exactly ONE real request to OpenRouter through the actual
copilot entry point (`answer_copilot_query`). It validates the response
against the `CopilotContent`/`CopilotAnswer`/`CopilotResponse` schemas and
runs the financial-safety validators on the generated content.

Opt-in: run only with `-m integration` and when `OPENAI_API_KEY` is set in
the local `backend/.env`. Skipped with `SKIPPED: missing configuration`
when credentials are absent.

No API key is ever printed. No production code is modified.
"""

from __future__ import annotations

import os
import tempfile
import time
import unittest
from datetime import date
from pathlib import Path

import httpx
import pytest
from dotenv import load_dotenv
from sqlalchemy import select

# Load local .env so OPENAI_API_KEY is visible to the skipif check below.
load_dotenv(
    dotenv_path=Path(__file__).resolve().parents[1] / ".env", override=True
)

from app.config import get_settings
from app.core.auth_rate_limit import _reset_all_limiters
from app.core.database import Base, configure_database, create_database
from app.database import get_db
from app.main import app
from app.models import (
    Employee,
    Employer,
    Employment,
    EwaPolicy,
    SalaryProfile,
    User,
    WageAccessRequest,
)
from app.schemas.ai_copilot import (
    CopilotResponse,
)
from app.services.ai_copilot import (
    FALLBACK_NOT_CONFIGURED,
    answer_copilot_query,
    contains_forbidden_recommendation,
    find_unsupported_amount,
    get_copilot_provider,
    reset_production_provider,
)

# Skip the entire module unless explicitly opted in AND credentials exist.
pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not os.getenv("OPENAI_API_KEY", "").strip(),
        reason="SKIPPED: missing configuration (OPENAI_API_KEY not set)",
    ),
]

CALC_DATE = date(2026, 2, 15)
TEST_MESSAGE = (
    "How much EWA is available to me this pay period, and what happens "
    "if I withdraw 30000 minor units?"
)


async def _register_user(client: httpx.AsyncClient) -> tuple[str, str]:
    resp = await client.post(
        "/auth/register",
        json={
            "email": "integration@example.com",
            "password": "password123",
            "name": "Integration Tester",
        },
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"], resp.json()["user_id"]


async def _setup_financial_profile(db, user_id: str) -> None:
    employer = Employer(id="emp-int", legal_name="Integration Co")
    db.add(employer)
    await db.commit()

    db.add(
        EwaPolicy(
            id="policy-int",
            employer_id=employer.id,
            enabled=True,
            max_access_percentage=50,
            max_withdrawals_per_period=3,
            minimum_tenure_days=7,
            minimum_remaining_salary_minor=1000,
            minimum_withdrawal_minor=2000,
            maximum_withdrawal_minor=50000,
        )
    )
    await db.commit()

    employee = Employee(id="emp-int-employee", user_id=user_id, status="active")
    db.add(employee)
    employment = Employment(
        id="emp-int-employment",
        employee_id=employee.id,
        employer_id=employer.id,
        status="active",
    )
    db.add(employment)
    db.add(
        SalaryProfile(
            id="sal-int",
            employment_id=employment.id,
            currency="USD",
            monthly_salary_amount_minor=1000000,
            pay_schedule="monthly",
            effective_from=date(2026, 1, 1),
            status="active",
        )
    )
    await db.commit()


class TestRealOpenRouterIntegration(unittest.IsolatedAsyncioTestCase):
    """Real OpenRouter integration via the actual copilot entry point."""

    async def asyncSetUp(self) -> None:
        _reset_all_limiters()
        self.temp_dir = tempfile.TemporaryDirectory()
        database_path = Path(self.temp_dir.name) / "integration.db"
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
        # Use the REAL production provider (no override) so the request goes
        # to OpenRouter. Reset any cached provider from previous tests.
        reset_production_provider()
        app.dependency_overrides.pop(get_copilot_provider, None)
        self.client = httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://testserver",
        )

    async def asyncTearDown(self) -> None:
        await self.client.aclose()
        app.dependency_overrides.clear()
        await self.engine.dispose()
        self.temp_dir.cleanup()
        reset_production_provider()
        if self.original_url:
            await configure_database(self.original_url)

    async def test_integration_real_openrouter_request(self) -> None:
        """One real OpenRouter request through answer_copilot_query.

        Validates:
        - Provider is OpenRouter and configured
        - Response validates against CopilotResponse schema
        - read_only=True and snapshot_only=True preserved
        - No unsupported amounts in generated text
        - No forbidden recommendations in generated text
        - Authoritative facts match the FinancialContext exactly
        - No WageAccessRequest created (read-only)
        """
        # Verify provider is real OpenRouter before making any request.
        provider = get_copilot_provider()
        assert provider.is_configured, "provider must be configured"
        assert provider.name == "openrouter", f"expected openrouter, got {provider.name}"
        assert provider.model == "deepseek/deepseek-v4.1-flash-1017"

        # Register user via API (same pattern as existing tests).
        _, user_id = await _register_user(self.client)

        # Call the actual entry point with real db + user + real provider.
        # Everything happens inside one async session.
        start = time.perf_counter()
        async with self.sessions() as db:
            await _setup_financial_profile(db, user_id)
            user = (
                await db.execute(select(User).where(User.id == user_id))
            ).scalar_one()
            chat: CopilotResponse = await answer_copilot_query(
                db=db,
                user=user,
                message=TEST_MESSAGE,
                calculation_date=CALC_DATE,
                provider=provider,
            )
        elapsed = time.perf_counter() - start

        # --- Schema validation ---
        assert isinstance(chat, CopilotResponse)
        assert chat.read_only is True
        assert chat.snapshot_only is True
        assert chat.ai_metadata is not None
        assert chat.ai_metadata.provider == "openrouter"
        assert chat.ai_metadata.model == "deepseek/deepseek-v4.1-flash-1017"

        # --- Authoritative facts match the FinancialContext exactly ---
        assert chat.authoritative_facts.earned_amount_minor == 500000
        assert chat.authoritative_facts.available_amount_minor == 250000
        assert chat.authoritative_facts.max_requestable_amount_minor == 50000
        assert chat.authoritative_facts.policy_limit_minor == 250000
        assert chat.authoritative_facts.salary_amount_minor == 1000000

        # --- Withdrawal analysis present (hypothetical, read-only) ---
        assert chat.withdrawal_analysis is not None
        assert chat.withdrawal_analysis.requested_amount_minor == 30000
        assert chat.withdrawal_analysis.snapshot_only is True

        # --- Financial safety: unsupported amounts in generated text ---
        if chat.ai_metadata.generated and not chat.ai_metadata.fallback_used:
            # Collect authoritative integer values for the amount guard.
            allowed = set()
            for v in chat.authoritative_facts.model_dump().values():
                if isinstance(v, int) and not isinstance(v, bool):
                    allowed.add(abs(v))
            if chat.withdrawal_analysis is not None:
                for v in chat.withdrawal_analysis.model_dump().values():
                    if isinstance(v, int) and not isinstance(v, bool):
                        allowed.add(abs(v))
            # The provider response text must not contain unsupported amounts.
            assert find_unsupported_amount(chat.response, allowed) is None, (
                f"unsupported amount in response: {chat.response[:200]}"
            )
            for fact in chat.key_facts:
                assert find_unsupported_amount(fact.text, allowed) is None, (
                    f"unsupported amount in key_fact {fact.code}: {fact.text[:200]}"
                )

        # --- Financial safety: no forbidden recommendations ---
        if chat.ai_metadata.generated and not chat.ai_metadata.fallback_used:
            assert contains_forbidden_recommendation(chat.response) is None, (
                f"forbidden recommendation in response: {chat.response[:200]}"
            )

        # --- Read-only: no WageAccessRequest created ---
        async with self.sessions() as db:
            count = (
                await db.execute(
                    select(WageAccessRequest).where(
                        WageAccessRequest.user_id == user_id
                    )
                )
            ).scalars().all()
            assert len(count) == 0, "no WageAccessRequest may be created by the copilot"

        # --- Latency sanity ---
        assert elapsed < 60, f"request took too long: {elapsed:.3f}s"

    async def test_integration_fallback_when_provider_misconfigured(self) -> None:
        """When no API key is set, the real provider returns deterministic fallback."""
        original_key = os.environ.get("OPENAI_API_KEY", "")
        os.environ["OPENAI_API_KEY"] = ""
        reset_production_provider()
        try:
            provider = get_copilot_provider()
            assert not provider.is_configured

            _, user_id = await _register_user(self.client)

            async with self.sessions() as db:
                await _setup_financial_profile(db, user_id)
                user = (
                    await db.execute(select(User).where(User.id == user_id))
                ).scalar_one()

                chat: CopilotResponse = await answer_copilot_query(
                    db=db,
                    user=user,
                    message="How much is available?",
                    calculation_date=CALC_DATE,
                    provider=provider,
                )
            assert chat.ai_metadata.fallback_used is True
            assert chat.ai_metadata.fallback_reason == FALLBACK_NOT_CONFIGURED
            assert chat.ai_metadata.generated is False
            assert chat.read_only is True
            assert chat.snapshot_only is True
        finally:
            os.environ["OPENAI_API_KEY"] = original_key
            reset_production_provider()
