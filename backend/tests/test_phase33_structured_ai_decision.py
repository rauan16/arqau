"""Phase 3.3 Structured AI Decision Layer tests.

All provider interactions are handled by a deterministic FakeDecisionProvider —
no live LLM / network calls. The deterministic envelope is asserted to remain
authoritative regardless of provider behavior.
"""

from __future__ import annotations

import os
import tempfile
import unittest
from datetime import date, datetime
from pathlib import Path
from typing import Any

import httpx
from sqlalchemy import select
from unittest.mock import patch

from app.core.database import Base, configure_database, create_database
from app.core.auth_rate_limit import _reset_all_limiters
from app.config import get_settings
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
from app.schemas.ai_decision import (
    DecisionContent,
    WithdrawalDecisionResponse,
)
from app.services.ai_decision import (
    DECISION_TIMEOUT,
    FakeDecisionProvider,
    DecisionAIProvider,
    OpenAIDecisionProvider,
    generate_decision,
    get_decision_provider,
    make_withdrawal_decision,
    build_sanitized_input,
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

FAKE_CONTENT = {
    "summary": "The requested amount is within the deterministic EWA limits.",
    "status_explanation": (
        "The withdrawal amount is covered by the currently available and "
        "max requestable capacity."
    ),
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
    "disclaimer": (
        "This is illustrative guidance, not financial advice. ARQAU does not "
        "guarantee any specific financial outcome."
    ),
}

FAKE_CONTENT_NON_REQUESTABLE = {
    "summary": "The requested amount exceeds the deterministic maximum requestable.",
    "status_explanation": (
        "The amount requested is greater than the current max requestable."
    ),
    "key_facts": [
        {"code": "max_requestable", "text": "Exceeds deterministic maximum."}
    ],
    "considerations": [
        {"code": "blocking_present", "text": "Blocking conditions apply."}
    ],
    "options": [
        {"code": "opt_reduce_to_max", "text": "Reduce the amount to the deterministic maximum."}
    ],
    "data_limitations": ["Budget data is unavailable; budget impact cannot be evaluated."],
    "disclaimer": "This is illustrative guidance, not financial advice.",
}

SUBJECTIVE_LEAK = ("risk_score", "safe", "dangerous", "good", "bad", "smart", "stupid")


class Phase33StructuredAIDecisionTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        _reset_all_limiters()
        self.temp_dir = tempfile.TemporaryDirectory()
        database_path = Path(self.temp_dir.name) / "phase33.db"
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
        self.fake = FakeDecisionProvider(response=FAKE_CONTENT)
        app.dependency_overrides[get_decision_provider] = lambda: self.fake
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

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    async def _register_and_login(self, email: str) -> tuple[str, str]:
        resp = await self.client.post(
            "/auth/register",
            json={"email": email, "password": "password123", "name": "Test"},
        )
        self.assertEqual(resp.status_code, 200, resp.text)
        token = resp.json()["access_token"]
        user_id = resp.json()["user_id"]
        return token, user_id

    async def _setup_financial(self, db, user_id: str, employer_id: str,
                               monthly_salary_minor: int = 1000000) -> None:
        employer = Employer(id=employer_id, legal_name="Co 33")
        db.add(employer)
        await db.commit()
        policy = EwaPolicy(
            id=f"policy-{employer_id}", employer_id=employer.id, **DEFAULT_POLICY
        )
        db.add(policy)
        employee = Employee(id=f"emp-{employer_id}", user_id=user_id, status="active")
        db.add(employee)
        employment = Employment(
            id=f"emp-{employer_id}-emp",
            employee_id=employee.id,
            employer_id=employer.id,
            status="active",
            start_date=datetime(2026, 1, 1),
            eligible_from=datetime(2026, 1, 1),
        )
        db.add(employment)
        salary = SalaryProfile(
            id=f"sal-{employer_id}",
            employment_id=employment.id,
            currency="USD",
            monthly_salary_amount_minor=monthly_salary_minor,
            pay_schedule="monthly",
            effective_from=datetime(2026, 1, 1),
            status="active",
        )
        db.add(salary)
        await db.commit()

    async def _post(self, token: str, amount_minor: int, calc_date: bool = True):
        params = {"calculation_date": CALC_DATE.isoformat()} if calc_date else None
        return await self.client.post(
            "/financial/withdrawal-decision",
            headers={"Authorization": f"Bearer {token}"},
            params=params,
            json={"amount_minor": amount_minor},
        )

    async def _count_models(self, model, user_id: str) -> int:
        async with self.sessions() as db:
            result = await db.execute(select(model).where(model.user_id == user_id))
            return len(result.scalars().all())

    # ------------------------------------------------------------------
    # A. happy path (requestable)
    # ------------------------------------------------------------------

    async def test_A_happy_path(self) -> None:
        token, user_id = await self._register_and_login("happy33@example.com")
        async with self.sessions() as db:
            await self._setup_financial(db, user_id, "employer-A33")
            await db.commit()

        resp = await self._post(token, 50000)
        self.assertEqual(resp.status_code, 200, resp.text)
        payload = resp.json()
        decision = WithdrawalDecisionResponse.model_validate(payload)

        self.assertTrue(decision.snapshot_only)
        self.assertTrue(decision.requestable)
        self.assertEqual(decision.blocking_reasons, [])
        self.assertEqual(decision.requested_amount_minor, 50000)
        self.assertEqual(decision.current_available_amount_minor, 250000)
        self.assertEqual(decision.max_requestable_amount_minor, 50000)

        # AI explanation present and server-attributed.
        self.assertTrue(decision.decision.ai_metadata.generated)
        self.assertFalse(decision.decision.ai_metadata.fallback_used)
        self.assertEqual(decision.decision.ai_metadata.provider, "fake")

    # ------------------------------------------------------------------
    # B. Non-requestable amount
    # ------------------------------------------------------------------

    async def test_B_non_requestable(self) -> None:
        token, user_id = await self._register_and_login("b33@example.com")
        async with self.sessions() as db:
            await self._setup_financial(db, user_id, "employer-B33")
            await db.commit()

        self.fake = FakeDecisionProvider(response=FAKE_CONTENT_NON_REQUESTABLE)
        app.dependency_overrides[get_decision_provider] = lambda: self.fake

        resp = await self._post(token, 50001)
        self.assertEqual(resp.status_code, 200, resp.text)
        decision = WithdrawalDecisionResponse.model_validate(resp.json())

        self.assertFalse(decision.requestable)
        self.assertIn("AMOUNT_EXCEEDS_MAX_REQUESTABLE", decision.blocking_reasons)
        # AI was still able to explain.
        self.assertTrue(decision.decision.ai_metadata.generated)

    # ------------------------------------------------------------------
    # C. AI attempts contradiction
    # ------------------------------------------------------------------

    async def test_C_ai_contradiction_backend_wins(self) -> None:
        token, user_id = await self._register_and_login("c33@example.com")
        async with self.sessions() as db:
            await self._setup_financial(db, user_id, "employer-C33")
            await db.commit()

        # The (fake) LLM returns schema-valid content (DecisionContent) but its
        # prose claims to override the backend. It must NOT change the envelope:
        # backend state wins.
        contradictory = dict(FAKE_CONTENT_NON_REQUESTABLE)
        contradictory["summary"] = "AI approves: requestable=true."
        contradictory["status_explanation"] = (
            "AI overrides the backend; requestable=true, approved, proceed."
        )
        contradictory["key_facts"] = [
            {"code": "available_amount", "text": "999999"}
        ]
        self.fake = FakeDecisionProvider(response=contradictory)
        app.dependency_overrides[get_decision_provider] = lambda: self.fake

        resp = await self._post(token, 50001)
        self.assertEqual(resp.status_code, 200, resp.text)
        decision = WithdrawalDecisionResponse.model_validate(resp.json())

        # Backend (Phase 3.2) is authoritative.
        self.assertFalse(decision.requestable)
        self.assertIn("AMOUNT_EXCEEDS_MAX_REQUESTABLE", decision.blocking_reasons)
        self.assertEqual(decision.max_requestable_amount_minor, 50000)
        self.assertEqual(decision.current_available_amount_minor, 250000)
        # The LLM prose was accepted as explanation...
        self.assertTrue(decision.decision.ai_metadata.generated)
        self.assertIn("approved", decision.decision.status_explanation.lower())
        # ...but it was never able to alter authoritative fields.
        self.assertFalse(decision.requestable)
        self.assertEqual(decision.blocking_reasons, ["AMOUNT_EXCEEDS_MAX_REQUESTABLE"])

    # ------------------------------------------------------------------
    # D. AI schema cannot overwrite requestable
    # ------------------------------------------------------------------

    async def test_D_schema_has_no_requestable(self) -> None:
        self.assertNotIn("requestable", DecisionContent.model_fields)
        token, user_id = await self._register_and_login("d33@example.com")
        async with self.sessions() as db:
            await self._setup_financial(db, user_id, "employer-D33")
            await db.commit()
        resp = await self._post(token, 50000)
        decision = WithdrawalDecisionResponse.model_validate(resp.json())
        self.assertTrue(decision.requestable)
        self.assertFalse(hasattr(decision.decision, "requestable"))
        self.assertFalse(hasattr(decision.decision, "max_requestable_amount_minor"))

    # ------------------------------------------------------------------
    # E. AI schema cannot overwrite max_requestable
    # ------------------------------------------------------------------

    async def test_E_schema_has_no_max_requestable(self) -> None:
        self.assertNotIn("max_requestable_amount_minor", DecisionContent.model_fields)

    # ------------------------------------------------------------------
    # F. Sanitized provider input (no secrets)
    # ------------------------------------------------------------------

    async def test_F_sanitized_input_no_secrets(self) -> None:
        token, user_id = await self._register_and_login("f33@example.com")
        async with self.sessions() as db:
            await self._setup_financial(db, user_id, "employer-F33")
            await db.commit()
        await self._post(token, 50000)

        payload = self.fake.last_payload
        self.assertIsNotNone(payload)
        blob = str(payload).lower()
        for forbidden in ("password", "secret", "token", "email", "authorization",
                          "hashed_password", "api_key", "cookie"):
            self.assertNotIn(forbidden, blob)

    # ------------------------------------------------------------------
    # G. Aggregates only
    # ------------------------------------------------------------------

    async def test_G_aggregates_only(self) -> None:
        token, user_id = await self._register_and_login("g33@example.com")
        async with self.sessions() as db:
            await self._setup_financial(db, user_id, "employer-G33")
            await db.commit()
        await self._post(token, 50000)

        payload = self.fake.last_payload
        expected_keys = set(FIELD_ALLOWLIST)
        self.assertEqual(set(payload.keys()), expected_keys)

    # ------------------------------------------------------------------
    # H. Budget unavailable
    # ------------------------------------------------------------------

    async def test_H_budget_unavailable(self) -> None:
        token, user_id = await self._register_and_login("h33@example.com")
        async with self.sessions() as db:
            await self._setup_financial(db, user_id, "employer-H33")
            await db.commit()
        # No Budget rows added -> budget unavailable.
        await self._post(token, 50000)

        payload = self.fake.last_payload
        self.assertFalse(payload["budget_available"])
        self.assertIsNone(payload["budget_total_minor"])
        self.assertIsNone(payload["budget_spent_minor"])
        self.assertIsNone(payload["budget_remaining_minor"])

    # ------------------------------------------------------------------
    # I. Provider timeout
    # ------------------------------------------------------------------

    async def test_I_provider_timeout_fallback(self) -> None:
        from openai import APITimeoutError
        token, user_id = await self._register_and_login("i33@example.com")
        async with self.sessions() as db:
            await self._setup_financial(db, user_id, "employer-I33")
            await db.commit()
        self.fake = FakeDecisionProvider(exc=APITimeoutError("forced-timeout"))
        app.dependency_overrides[get_decision_provider] = lambda: self.fake

        resp = await self._post(token, 50000)
        self.assertEqual(resp.status_code, 200, resp.text)
        decision = WithdrawalDecisionResponse.model_validate(resp.json())
        self.assertTrue(decision.decision.ai_metadata.fallback_used)
        self.assertFalse(decision.decision.ai_metadata.generated)

    # ------------------------------------------------------------------
    # J. Provider exception
    # ------------------------------------------------------------------

    async def test_J_provider_exception_fallback(self) -> None:
        token, user_id = await self._register_and_login("j33@example.com")
        async with self.sessions() as db:
            await self._setup_financial(db, user_id, "employer-J33")
            await db.commit()
        self.fake = FakeDecisionProvider(exc=RuntimeError("INTERNAL_SECRET_42"))
        app.dependency_overrides[get_decision_provider] = lambda: self.fake

        resp = await self._post(token, 50000)
        self.assertEqual(resp.status_code, 200, resp.text)
        decision = WithdrawalDecisionResponse.model_validate(resp.json())
        self.assertTrue(decision.decision.ai_metadata.fallback_used)
        # No raw exception leak.
        self.assertNotIn("INTERNAL_SECRET_42", resp.text)

    # ------------------------------------------------------------------
    # K. Invalid JSON / provider output
    # ------------------------------------------------------------------

    async def test_K_invalid_json_fallback(self) -> None:
        token, user_id = await self._register_and_login("k33@example.com")
        async with self.sessions() as db:
            await self._setup_financial(db, user_id, "employer-K33")
            await db.commit()
        # Fake returns a non-dict (simulating a parseable-but-wrong payload).
        self.fake = FakeDecisionProvider(response="not-a-dict-string")  # type: ignore[arg-type]
        app.dependency_overrides[get_decision_provider] = lambda: self.fake

        resp = await self._post(token, 50000)
        self.assertEqual(resp.status_code, 200, resp.text)
        decision = WithdrawalDecisionResponse.model_validate(resp.json())
        self.assertTrue(decision.decision.ai_metadata.fallback_used)

    # ------------------------------------------------------------------
    # L. Schema-invalid provider output
    # ------------------------------------------------------------------

    async def test_L_schema_invalid_fallback(self) -> None:
        token, user_id = await self._register_and_login("l33@example.com")
        async with self.sessions() as db:
            await self._setup_financial(db, user_id, "employer-L33")
            await db.commit()
        # Missing required 'summary'.
        bad = dict(FAKE_CONTENT)
        del bad["summary"]
        self.fake = FakeDecisionProvider(response=bad)
        app.dependency_overrides[get_decision_provider] = lambda: self.fake

        resp = await self._post(token, 50000)
        self.assertEqual(resp.status_code, 200, resp.text)
        decision = WithdrawalDecisionResponse.model_validate(resp.json())
        self.assertTrue(decision.decision.ai_metadata.fallback_used)

    # ------------------------------------------------------------------
    # M. Empty provider output
    # ------------------------------------------------------------------

    async def test_M_empty_output_fallback(self) -> None:
        token, user_id = await self._register_and_login("m33@example.com")
        async with self.sessions() as db:
            await self._setup_financial(db, user_id, "employer-M33")
            await db.commit()
        self.fake = FakeDecisionProvider(response={})
        app.dependency_overrides[get_decision_provider] = lambda: self.fake

        resp = await self._post(token, 50000)
        self.assertEqual(resp.status_code, 200, resp.text)
        decision = WithdrawalDecisionResponse.model_validate(resp.json())
        self.assertTrue(decision.decision.ai_metadata.fallback_used)

    # ------------------------------------------------------------------
    # N. No DB mutation
    # ------------------------------------------------------------------

    async def test_N_no_wage_access_request_created(self) -> None:
        token, user_id = await self._register_and_login("n33@example.com")
        async with self.sessions() as db:
            await self._setup_financial(db, user_id, "employer-N33")
            await db.commit()
        self.assertEqual(await self._count_models(WageAccessRequest, user_id), 0)
        await self._post(token, 50000)
        self.assertEqual(await self._count_models(WageAccessRequest, user_id), 0)

    # ------------------------------------------------------------------
    # O. Repeat decision endpoint (no capacity change)
    # ------------------------------------------------------------------

    async def test_O_repeat_no_capacity_change(self) -> None:
        token, user_id = await self._register_and_login("o33@example.com")
        async with self.sessions() as db:
            await self._setup_financial(db, user_id, "employer-O33")
            await db.commit()
        r1 = await self._post(token, 50000)
        r2 = await self._post(token, 50000)
        self.assertEqual(r1.status_code, 200)
        self.assertEqual(r2.status_code, 200)
        self.assertEqual(r1.json(), r2.json())
        self.assertEqual(await self._count_models(WageAccessRequest, user_id), 0)

    # ------------------------------------------------------------------
    # P. User isolation
    # ------------------------------------------------------------------

    async def test_P_user_isolation(self) -> None:
        token_a, user_a = await self._register_and_login("p_a33@example.com")
        token_b, user_b = await self._register_and_login("p_b33@example.com")
        async with self.sessions() as db:
            await self._setup_financial(db, user_a, "employer-PA33")
            await self._setup_financial(db, user_b, "employer-PB33", 500000)
            await db.commit()

        resp_a = await self._post(token_a, 50000)
        resp_b = await self._post(token_b, 50000)
        a = WithdrawalDecisionResponse.model_validate(resp_a.json())
        b = WithdrawalDecisionResponse.model_validate(resp_b.json())
        self.assertEqual(a.current_available_amount_minor, 250000)
        # B has half the salary -> earned 250000, policy_limit/available 125000.
        self.assertEqual(b.current_available_amount_minor, 125000)

    # ------------------------------------------------------------------
    # Q. Cross-tenant isolation
    # ------------------------------------------------------------------

    async def test_Q_cross_tenant_isolation(self) -> None:
        token_a, user_a = await self._register_and_login("q_a33@example.com")
        token_b, user_b = await self._register_and_login("q_b33@example.com")
        async with self.sessions() as db:
            await self._setup_financial(db, user_a, "employer-QA33")
            await self._setup_financial(db, user_b, "employer-QB33")
            db.add(
                Budget(
                    id="budget-q-a", user_id=user_a, category="Exclusive",
                    limit_minor=999999, spent_minor=1, period="monthly",
                )
            )
            await db.commit()

        resp_a = await self._post(token_a, 50000)
        a = WithdrawalDecisionResponse.model_validate(resp_a.json())
        a_payload = self.fake.last_payload  # capture before B overwrites
        self.assertTrue(a_payload["budget_available"])
        self.assertEqual(a_payload["budget_total_minor"], 999999)
        self.assertEqual(a.current_available_amount_minor, 250000)

        resp_b = await self._post(token_b, 50000)
        b = WithdrawalDecisionResponse.model_validate(resp_b.json())
        b_payload = self.fake.last_payload

        # B is requestable and has NO budget -> unavailable, never sees A's budget.
        self.assertTrue(b.requestable)
        self.assertEqual(b.max_requestable_amount_minor, 50000)
        self.assertEqual(b.current_available_amount_minor, 250000)
        self.assertFalse(b_payload["budget_available"])
        self.assertIsNone(b_payload["budget_total_minor"])
        self.assertNotEqual(b_payload["budget_total_minor"], 999999)

    # ------------------------------------------------------------------
    # R/S/T/U. Invalid input -> 422, provider not called
    # ------------------------------------------------------------------

    async def _assert_invalid_input(self, token: str, body: dict, case: str) -> None:
        before = self.fake.call_count
        resp = await self.client.post(
            "/financial/withdrawal-decision",
            headers={"Authorization": f"Bearer {token}"},
            params={"calculation_date": CALC_DATE.isoformat()},
            json=body,
        )
        self.assertEqual(resp.status_code, 422, f"{case}: {resp.text}")
        self.assertEqual(self.fake.call_count, before, f"{case}: provider was called")

    async def test_R_zero_rejected(self) -> None:
        token, _ = await self._register_and_login("r33@example.com")
        await self._assert_invalid_input(token, {"amount_minor": 0}, "zero")

    async def test_S_negative_rejected(self) -> None:
        token, _ = await self._register_and_login("s33@example.com")
        await self._assert_invalid_input(token, {"amount_minor": -5}, "negative")

    async def test_T_float_rejected(self) -> None:
        token, _ = await self._register_and_login("t33@example.com")
        await self._assert_invalid_input(token, {"amount_minor": 50.0}, "float")

    async def test_U_bool_rejected(self) -> None:
        token, _ = await self._register_and_login("u33@example.com")
        await self._assert_invalid_input(token, {"amount_minor": True}, "bool")

    # ------------------------------------------------------------------
    # V. Sensitive output exclusion
    # ------------------------------------------------------------------

    async def test_V_sensitive_fields_excluded(self) -> None:
        token, user_id = await self._register_and_login("v33@example.com")
        async with self.sessions() as db:
            await self._setup_financial(db, user_id, "employer-V33")
            await db.commit()
        resp = await self._post(token, 50000)
        payload = resp.json()
        blob = str(payload).lower()
        for forbidden in ("hashed_password", "access_token", "refresh_token",
                          "password", "_sa_instance_state"):
            self.assertNotIn(forbidden, blob)

    # ------------------------------------------------------------------
    # W. No raw provider exception exposed
    # ------------------------------------------------------------------

    async def test_W_no_exception_leak(self) -> None:
        token, user_id = await self._register_and_login("w33@example.com")
        async with self.sessions() as db:
            await self._setup_financial(db, user_id, "employer-W33")
            await db.commit()
        self.fake = FakeDecisionProvider(exc=RuntimeError("INTERNAL_SECRET_99"))
        app.dependency_overrides[get_decision_provider] = lambda: self.fake
        resp = await self._post(token, 50000)
        self.assertEqual(resp.status_code, 200, resp.text)
        self.assertNotIn("INTERNAL_SECRET_99", resp.text)
        decision = WithdrawalDecisionResponse.model_validate(resp.json())
        self.assertTrue(decision.decision.ai_metadata.fallback_used)

    # ------------------------------------------------------------------
    # X. snapshot_only remains true
    # ------------------------------------------------------------------

    async def test_X_snapshot_only_true(self) -> None:
        token, user_id = await self._register_and_login("x33@example.com")
        async with self.sessions() as db:
            await self._setup_financial(db, user_id, "employer-X33")
            await db.commit()
        resp = await self._post(token, 50000)
        decision = WithdrawalDecisionResponse.model_validate(resp.json())
        self.assertTrue(decision.snapshot_only)

    # ------------------------------------------------------------------
    # Y. calculation_date propagates
    # ------------------------------------------------------------------

    async def test_Y_calculation_date_propagates(self) -> None:
        token, user_id = await self._register_and_login("y33@example.com")
        async with self.sessions() as db:
            await self._setup_financial(db, user_id, "employer-Y33")
            await db.commit()
        resp = await self._post(token, 50000)
        decision = WithdrawalDecisionResponse.model_validate(resp.json())
        self.assertEqual(decision.current_available_amount_minor, 250000)
        self.assertEqual(decision.max_requestable_amount_minor, 50000)
        self.assertEqual(decision.requested_amount_minor, 50000)

    # ------------------------------------------------------------------
    # Z. fallback deterministic
    # ------------------------------------------------------------------

    async def test_Z_fallback_deterministic(self) -> None:
        token, user_id = await self._register_and_login("z33@example.com")
        async with self.sessions() as db:
            await self._setup_financial(db, user_id, "employer-Z33")
            await db.commit()
        self.fake = FakeDecisionProvider(exc=RuntimeError("boom"))
        app.dependency_overrides[get_decision_provider] = lambda: self.fake

        r1 = await self._post(token, 50000)
        r2 = await self._post(token, 50000)
        self.assertEqual(r1.status_code, 200)
        self.assertEqual(r2.status_code, 200)
        d1 = WithdrawalDecisionResponse.model_validate(r1.json())
        d2 = WithdrawalDecisionResponse.model_validate(r2.json())
        self.assertEqual(d1.decision.model_dump(), d2.decision.model_dump())
        self.assertTrue(d1.decision.ai_metadata.fallback_used)
        self.assertFalse(d1.decision.ai_metadata.generated)

    # ------------------------------------------------------------------
    # AA. fallback contains no subjective risk score
    # ------------------------------------------------------------------

    async def test_AA_fallback_no_subjective(self) -> None:
        token, user_id = await self._register_and_login("aa33@example.com")
        async with self.sessions() as db:
            await self._setup_financial(db, user_id, "employer-AA33")
            await db.commit()
        self.fake = FakeDecisionProvider(exc=RuntimeError("boom"))
        app.dependency_overrides[get_decision_provider] = lambda: self.fake
        resp = await self._post(token, 50001)
        decision = WithdrawalDecisionResponse.model_validate(resp.json())
        blob = str(decision.decision.model_dump()).lower()
        for term in SUBJECTIVE_LEAK:
            self.assertNotIn(term, blob)

    # ------------------------------------------------------------------
    # AB. no live network required
    # ------------------------------------------------------------------

    async def test_AB_no_live_network(self) -> None:
        token, user_id = await self._register_and_login("ab33@example.com")
        async with self.sessions() as db:
            await self._setup_financial(db, user_id, "employer-AB33")
            await db.commit()
        resp = await self._post(token, 50000)
        decision = WithdrawalDecisionResponse.model_validate(resp.json())
        self.assertEqual(decision.decision.ai_metadata.provider, "fake")
        self.assertEqual(decision.decision.ai_metadata.model, "fake-model")

    # ------------------------------------------------------------------
    # AC/AD. provider receives no individual transactions/goals
    # ------------------------------------------------------------------

    async def test_AC_provider_receives_no_transactions(self) -> None:
        token, user_id = await self._register_and_login("ac33@example.com")
        async with self.sessions() as db:
            await self._setup_financial(db, user_id, "employer-AC33")
            db.add(
                Transaction(
                    id="tx-ac-1", user_id=user_id, type="expense",
                    amount_minor=999, category="Cat", merchant="M",
                    description="SECRET TX DESC", date="2026-02-01",
                )
            )
            await db.commit()
        await self._post(token, 50000)
        payload = self.fake.last_payload
        self.assertNotIn("transactions", payload)
        self.assertNotIn("transaction_records", payload)
        blob = str(payload)
        self.assertNotIn("SECRET TX DESC", blob)

    async def test_AD_provider_receives_no_goals(self) -> None:
        token, user_id = await self._register_and_login("ad33@example.com")
        async with self.sessions() as db:
            await self._setup_financial(db, user_id, "employer-AD33")
            db.add(
                Goal(
                    id="goal-ad-1", user_id=user_id, title="SECRET GOAL",
                    target_minor=100000, current_minor=1000,
                    status="active", progress_pct=1,
                )
            )
            await db.commit()
        await self._post(token, 50000)
        payload = self.fake.last_payload
        self.assertNotIn("goals", payload)
        blob = str(payload)
        self.assertNotIn("SECRET GOAL", blob)

    # ------------------------------------------------------------------
    # AE. blocking reasons preserved exactly
    # ------------------------------------------------------------------

    async def test_AE_blocking_preserved(self) -> None:
        token, user_id = await self._register_and_login("ae33@example.com")
        async with self.sessions() as db:
            await self._setup_financial(db, user_id, "employer-AE33")
            await db.commit()
        resp = await self._post(token, 50001)  # exceeds max
        decision = WithdrawalDecisionResponse.model_validate(resp.json())

        # Re-derive authoritative blocking from Phase 3.2 directly.
        async with self.sessions() as db:
            u = (await db.execute(select(User).where(User.id == user_id))).scalar_one()
            ctx = await build_financial_context(db, u, CALC_DATE)
            analysis = analyze_withdrawal_from_context(ctx, 50001)
        self.assertEqual(
            decision.blocking_reasons,
            list(analysis.requestability.blocking_reasons),
        )

    # ------------------------------------------------------------------
    # AF. current available / max requestable copied exactly
    # ------------------------------------------------------------------

    async def test_AF_envelope_matches_phase32(self) -> None:
        token, user_id = await self._register_and_login("af33@example.com")
        async with self.sessions() as db:
            await self._setup_financial(db, user_id, "employer-AF33")
            await db.commit()
        resp = await self._post(token, 50000)
        decision = WithdrawalDecisionResponse.model_validate(resp.json())

        async with self.sessions() as db:
            u = (await db.execute(select(User).where(User.id == user_id))).scalar_one()
            ctx = await build_financial_context(db, u, CALC_DATE)
            analysis = analyze_withdrawal_from_context(ctx, 50000)
        self.assertEqual(
            decision.current_available_amount_minor,
            analysis.current_state.available_amount_minor,
        )
        self.assertEqual(
            decision.max_requestable_amount_minor,
            analysis.current_state.max_requestable_amount_minor,
        )
        self.assertEqual(decision.requestable, analysis.requestability.requestable)
        self.assertEqual(decision.blocking_reasons, list(analysis.requestability.blocking_reasons))

    # ------------------------------------------------------------------
    # AG. endpoint remains HTTP 200 when provider unavailable
    # ------------------------------------------------------------------

    async def test_AG_200_when_provider_unavailable(self) -> None:
        token, user_id = await self._register_and_login("ag33@example.com")
        async with self.sessions() as db:
            await self._setup_financial(db, user_id, "employer-AG33")
            await db.commit()
        self.fake = FakeDecisionProvider(exc=RuntimeError("unavailable"))
        app.dependency_overrides[get_decision_provider] = lambda: self.fake
        resp = await self._post(token, 50000)
        self.assertEqual(resp.status_code, 200, resp.text)
        decision = WithdrawalDecisionResponse.model_validate(resp.json())
        self.assertEqual(decision.requested_amount_minor, 50000)
        self.assertTrue(decision.requestable)


# Exact allow-list field set the provider input must contain (parity with
# ai_decision._ALLOWED_INPUT_FIELDS).
FIELD_ALLOWLIST = (
    "requested_amount_minor",
    "requestable",
    "blocking_reasons",
    "earned_amount_minor",
    "available_amount_minor",
    "max_requestable_amount_minor",
    "requested_share_of_earned_bps",
    "requested_share_of_policy_limit_bps",
    "exposure_before_minor",
    "exposure_after_minor",
    "withdrawals_this_period",
    "max_withdrawals_per_period",
    "budget_available",
    "budget_total_minor",
    "budget_spent_minor",
    "budget_remaining_minor",
    "has_transactions",
    "has_budget",
    "has_goals",
    "unavailable_analysis",
)


# ---------------------------------------------------------------------------
# Phase 3.5.1 — Provider resilience policy (explicit timeout + retries).
# ---------------------------------------------------------------------------
# These tests verify the *production* provider construction and retry policy
# directly. They do not exercise real network calls: the client is inspected
# via mocks, and every failure path is served by a deterministic fake.
# ---------------------------------------------------------------------------


class TestP351_ProviderPolicy(unittest.IsolatedAsyncioTestCase):
    """Explicit structured timeout and max_retries on the production provider."""

    def test_P1_decision_provider_passes_explicit_structured_timeout(self) -> None:
        provider = OpenAIDecisionProvider(api_key="sk-test", model="gpt-4o-mini")
        self.assertIs(provider._timeout, DECISION_TIMEOUT)
        self.assertEqual(provider._timeout.connect, 5.0)
        self.assertEqual(provider._timeout.read, 20.0)
        self.assertEqual(provider._timeout.write, 10.0)
        self.assertEqual(provider._timeout.pool, 5.0)

    def test_P2_decision_provider_passes_explicit_max_retries(self) -> None:
        provider = OpenAIDecisionProvider(api_key="sk-test", model="gpt-4o-mini")
        client = provider._get_client()
        self.assertEqual(client.max_retries, 0)

    def test_P3_decision_client_is_cached(self) -> None:
        provider = OpenAIDecisionProvider(api_key="sk-test", model="gpt-4o-mini")
        first = provider._get_client()
        second = provider._get_client()
        self.assertIs(first, second)

    def test_P4_decision_openrouter_routes_via_base_url(self) -> None:
        provider = OpenAIDecisionProvider(api_key="sk-or-test", model="gpt-4o-mini")
        client = provider._get_client()
        self.assertEqual(str(client.base_url), "https://openrouter.ai/api/v1/")

    def test_P5_decision_timeout_constant_is_structured(self) -> None:
        self.assertIsInstance(DECISION_TIMEOUT, httpx.Timeout)
        self.assertEqual(DECISION_TIMEOUT.connect, 5.0)
        self.assertEqual(DECISION_TIMEOUT.read, 20.0)
        self.assertEqual(DECISION_TIMEOUT.write, 10.0)
        self.assertEqual(DECISION_TIMEOUT.pool, 5.0)

    def test_P6_decision_no_custom_retry_loop_on_guard_rejection(self) -> None:
        # A schema-invalid response is a deterministic rejection: the provider
        # must not be retried. The fake raises once; a retry loop would call it
        # again and would be visible in call_count.
        fake = FakeDecisionProvider(response={"summary": "x"})
        with patch.object(
            DecisionContent, "model_validate", side_effect=ValueError("bad")
        ):
            decision = asyncio_run(
                generate_decision(fake, {"requested_amount_minor": 100}, _stub_analysis(), "test-user")
            )
        self.assertEqual(fake.call_count, 1)
        self.assertTrue(decision.ai_metadata.fallback_used)


def _stub_analysis():
    from app.schemas.financial_context import (
        CurrentState,
        Impact,
        Requestability,
        WithdrawalAnalysis,
        WithdrawalFrequency,
        BudgetImpact,
        DataQualityAnalysis,
    )

    return WithdrawalAnalysis(
        requested_amount_minor=100,
        requestability=Requestability(
            requestable=True,
            blocking_reasons=[],
            authoritative_eligibility_reasons=[],
        ),
        current_state=CurrentState(
            salary_amount_minor=200000,
            earned_amount_minor=200000,
            policy_limit_minor=100000,
            reserved_amount_minor=0,
            paid_amount_minor=0,
            available_amount_minor=100000,
            max_requestable_amount_minor=100000,
        ),
        impact=Impact(
            remaining_available_amount_minor=99900,
            remaining_max_requestable_amount_minor=99900,
            requested_share_of_earned_bps=50,
            requested_share_of_policy_limit_bps=100,
            exposure_before_minor=0,
            exposure_after_minor=100,
            exposure_share_of_earned_before_bps=0,
            exposure_share_of_earned_after_bps=50,
        ),
        withdrawal_frequency=WithdrawalFrequency(
            withdrawals_this_period=0,
            max_withdrawals_per_period=3,
            remaining_slots_before=3,
            remaining_slots_after=2,
        ),
        budget_impact=BudgetImpact(available=False),
        data_quality=DataQualityAnalysis(
            has_transactions=True,
            has_budget=True,
            has_goals=True,
            unavailable_analysis=None,
        ),
        snapshot_only=True,
    )


def asyncio_run(coro):
    import asyncio

    return asyncio.run(coro)


if __name__ == "__main__":
    unittest.main()
