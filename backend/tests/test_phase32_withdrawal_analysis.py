"""Phase 3.2 Deterministic Withdrawal Analysis Engine Tests.

Covers:
 1. happy path
 2. FinancialContext EWA consistency
 3. exceeds max requestable
 4. below minimum
 5. EWA ineligible
 6. can_request false
 7. withdrawal limit reached
 8. basis-point floor math
 9. zero denominator
10. exposure math
11. budget available
12. budget unavailable
13. transactions/goals unchanged
14. no WageAccessRequest created
15. repeated analysis causes no capacity change
16. user isolation
17. cross-tenant isolation
18. zero rejected
19. negative rejected
20. float rejected
21. sensitive fields excluded
22. no float financial output
23. amount == max_requestable
24. amount == minimum
25. calculation_date determinism
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

from app.core.database import Base, configure_database, create_database
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
from app.schemas.financial_context import (
    BudgetContext,
    DataQualityAnalysis,
    DataQualityContext,
    EwaContext,
    FinancialContext,
    GoalsContext,
    IncomeContext,
    SpendingContext,
    WithdrawalAnalysis,
    WithdrawalAnalysisRequest,
)
from app.services.financial_context_service import (
    analyze_withdrawal_from_context,
)

os.environ.setdefault("APP_ENV", "testing")
os.environ.setdefault("SECRET_KEY", "test-secret")
os.environ.setdefault("OPENAI_API_KEY", "test-key")

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


def _default_ewa(**overrides: Any) -> EwaContext:
    values = dict(
        earned_amount_minor=500000,
        policy_limit_minor=250000,
        reserved_amount_minor=0,
        paid_amount_minor=0,
        available_amount_minor=250000,
        max_requestable_amount_minor=50000,
        pay_period_start=date(2026, 2, 1),
        pay_period_end=date(2026, 2, 28),
        calculation_date=CALC_DATE,
        salary_amount_minor=1000000,
        eligible=True,
        eligibility_reasons=tuple(),
        minimum_withdrawal_minor=2000,
        maximum_withdrawal_minor=50000,
        can_request_withdrawal=True,
        max_withdrawals_per_period=3,
        withdrawals_this_period=0,
    )
    values.update(overrides)
    return EwaContext(**values)


def _make_context(**ewa_overrides: Any) -> FinancialContext:
    """Build a fully-formed FinancialContext (no DB) for pure-logic tests."""
    return FinancialContext(
        user_id="user-pure",
        generated_at="2026-02-15T00:00:00",
        calculation_date=CALC_DATE,
        ewa=_default_ewa(**ewa_overrides),
        spending=SpendingContext(available=True, transaction_count=1),
        budget=BudgetContext(available=False),
        goals=GoalsContext(available=False),
        data_quality=DataQualityContext(
            has_salary_profile=True,
            has_ewa_policy=True,
            has_transactions=True,
            has_budget=False,
            has_goals=False,
            missing_data=[],
        ),
    )


class Phase32WithdrawalAnalysisTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        database_path = Path(self.temp_dir.name) / "wa.db"
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
        body = {"email": email, "password": "password123", "name": "Test"}
        resp = await self.client.post("/auth/register", json=body)
        self.assertEqual(resp.status_code, 200, resp.text)
        token = resp.json()["access_token"]
        user_id = resp.json()["user_id"]
        await self.client.post(
            "/auth/login", json={"email": email, "password": "password123"}
        )
        return token, user_id

    async def _setup_complete(
        self, db, user_id: str, employer_id: str
    ) -> dict:
        seq = getattr(self, "_seq", 0) + 1
        self._seq = seq
        suffix = f"-{seq}" if seq > 1 else ""
        employee = Employee(id=f"emp{suffix}", user_id=user_id, status="active")
        db.add(employee)
        employment = Employment(
            id=f"emp{suffix}-emp",
            employee_id=employee.id,
            employer_id=employer_id,
            status="active",
            start_date=datetime(2026, 1, 1),
            eligible_from=datetime(2026, 1, 1),
        )
        db.add(employment)
        salary = SalaryProfile(
            id=f"sal{suffix}",
            employment_id=employment.id,
            currency="USD",
            monthly_salary_amount_minor=1000000,
            pay_schedule="monthly",
            effective_from=datetime(2026, 1, 1),
            status="active",
        )
        db.add(salary)
        await db.commit()
        return {
            "employee_id": employee.id,
            "employment_id": employment.id,
            "salary_id": salary.id,
        }

    async def _add_policy(
        self, db, employer_id: str, **overrides: Any
    ) -> EwaPolicy:
        params = dict(DEFAULT_POLICY)
        params.update(overrides)
        policy = EwaPolicy(
            id=f"policy-{employer_id}", employer_id=employer_id, **params
        )
        db.add(policy)
        await db.commit()
        return policy

    async def _count_models(self, model, user_id: str) -> int:
        async with self.sessions() as db:
            result = await db.execute(select(model).where(model.user_id == user_id))
            return len(result.scalars().all())

    async def _count_wage_requests(self, user_id: str) -> int:
        return await self._count_models(WageAccessRequest, user_id)

    async def _count_transactions(self, user_id: str) -> int:
        return await self._count_models(Transaction, user_id)

    async def _count_goals(self, user_id: str) -> int:
        return await self._count_models(Goal, user_id)

    async def _count_budgets(self, user_id: str) -> int:
        return await self._count_models(Budget, user_id)

    async def _full_setup(
        self, token: str, user_id: str, employer_id: str, **policy_overrides: Any
    ) -> None:
        async with self.sessions() as db:
            employer = Employer(id=employer_id, legal_name="WA Corp")
            db.add(employer)
            await db.commit()
            await self._add_policy(db, employer.id, **policy_overrides)
            await self._setup_complete(db, user_id, employer.id)
            await db.commit()

    # ------------------------------------------------------------------
    # Pure-logic tests (no DB, deterministic)
    # ------------------------------------------------------------------

    def test_02_ewa_consistency(self) -> None:
        ctx = _make_context()
        analysis = analyze_withdrawal_from_context(ctx, 50000)

        ewa = ctx.ewa
        self.assertEqual(
            analysis.current_state.earned_amount_minor, ewa.earned_amount_minor
        )
        self.assertEqual(
            analysis.current_state.policy_limit_minor, ewa.policy_limit_minor
        )
        self.assertEqual(
            analysis.current_state.reserved_amount_minor, ewa.reserved_amount_minor
        )
        self.assertEqual(
            analysis.current_state.paid_amount_minor, ewa.paid_amount_minor
        )
        self.assertEqual(
            analysis.current_state.available_amount_minor,
            ewa.available_amount_minor,
        )
        self.assertEqual(
            analysis.current_state.max_requestable_amount_minor,
            ewa.max_requestable_amount_minor,
        )
        self.assertEqual(
            analysis.current_state.salary_amount_minor, ewa.salary_amount_minor
        )

    def test_08_basis_point_floor_math(self) -> None:
        ctx = _make_context(
            earned_amount_minor=3,
            policy_limit_minor=7,
            reserved_amount_minor=0,
            paid_amount_minor=0,
            available_amount_minor=7,
            max_requestable_amount_minor=7,
        )
        analysis = analyze_withdrawal_from_context(ctx, 1)

        # 1 * 10000 // 3 = 3333 (floor, not 3334)
        self.assertEqual(
            analysis.impact.requested_share_of_earned_bps, 3333
        )
        # 1 * 10000 // 7 = 1428 (floor, not 1429)
        self.assertEqual(
            analysis.impact.requested_share_of_policy_limit_bps, 1428
        )

    def test_09_zero_denominator(self) -> None:
        ctx = _make_context(
            earned_amount_minor=0,
            policy_limit_minor=0,
            reserved_amount_minor=100000,
            paid_amount_minor=50000,
            available_amount_minor=0,
            max_requestable_amount_minor=0,
            eligible=False,
            can_request_withdrawal=False,
            eligibility_reasons=("NO_EMPLOYMENT",),
            minimum_withdrawal_minor=None,
            max_withdrawals_per_period=None,
        )
        # Non-requestable path: ratios referencing earned (0) -> None
        analysis = analyze_withdrawal_from_context(ctx, 5)
        self.assertFalse(analysis.requestability.requestable)
        self.assertIsNone(analysis.impact.requested_share_of_earned_bps)
        self.assertIsNone(analysis.impact.requested_share_of_policy_limit_bps)
        self.assertIsNone(
            analysis.impact.exposure_share_of_earned_before_bps
        )
        self.assertIsNone(
            analysis.impact.exposure_share_of_earned_after_bps
        )

    def test_10_exposure_math(self) -> None:
        ctx = _make_context(
            earned_amount_minor=1000000,
            policy_limit_minor=275000,
            reserved_amount_minor=100000,
            paid_amount_minor=50000,
            available_amount_minor=275000,
            max_requestable_amount_minor=275000,
            max_withdrawals_per_period=3,
            withdrawals_this_period=1,
            minimum_withdrawal_minor=2000,
            maximum_withdrawal_minor=None,
        )
        analysis = analyze_withdrawal_from_context(ctx, 50000)

        self.assertTrue(analysis.requestability.requestable)
        # Exposure before = reserved + paid = 150000
        self.assertEqual(analysis.impact.exposure_before_minor, 150000)
        # Exposure after = 150000 + 50000 = 200000
        self.assertEqual(analysis.impact.exposure_after_minor, 200000)
        # remaining_available = 275000 - 50000 = 225000
        self.assertEqual(
            analysis.impact.remaining_available_amount_minor, 225000
        )
        # remaining_max_requestable = 275000 - 50000 = 225000
        self.assertEqual(
            analysis.impact.remaining_max_requestable_amount_minor, 225000
        )
        # slots before = 3 - 1 = 2 ; after = max(0, 2 - 1) = 1
        self.assertEqual(
            analysis.withdrawal_frequency.remaining_slots_before, 2
        )
        self.assertEqual(
            analysis.withdrawal_frequency.remaining_slots_after, 1
        )
        # exposure_share_of_earned_before = 150000 * 10000 // 1000000 = 1500
        self.assertEqual(
            analysis.impact.exposure_share_of_earned_before_bps, 1500
        )
        # exposure_share_of_earned_after = 200000 * 10000 // 1000000 = 2000
        self.assertEqual(
            analysis.impact.exposure_share_of_earned_after_bps, 2000
        )
        # requested_share_of_earned = 50000 * 10000 // 1000000 = 500
        self.assertEqual(
            analysis.impact.requested_share_of_earned_bps, 500
        )
        # requested_share_of_policy_limit = 50000 * 10000 // 275000 = 1818
        self.assertEqual(
            analysis.impact.requested_share_of_policy_limit_bps, 1818
        )

    def test_11_budget_available(self) -> None:
        ctx = _make_context()
        ctx.budget = BudgetContext(
            available=True,
            total_budget_minor=50000,
            spent_minor=20000,
            remaining_minor=30000,
        )
        analysis = analyze_withdrawal_from_context(ctx, 50000)

        self.assertTrue(analysis.budget_impact.available)
        self.assertEqual(analysis.budget_impact.total_budget_minor, 50000)
        self.assertEqual(analysis.budget_impact.current_spent_minor, 20000)
        self.assertEqual(analysis.budget_impact.current_remaining_minor, 30000)
        # 50000 * 10000 // 50000 = 10000
        self.assertEqual(
            analysis.budget_impact.withdrawal_share_of_budget_bps, 10000
        )

    def test_12_budget_unavailable(self) -> None:
        ctx = _make_context()
        analysis = analyze_withdrawal_from_context(ctx, 50000)

        self.assertFalse(analysis.budget_impact.available)
        self.assertIsNone(analysis.budget_impact.total_budget_minor)
        self.assertIsNone(analysis.budget_impact.current_spent_minor)
        self.assertIsNone(analysis.budget_impact.current_remaining_minor)
        self.assertIsNone(
            analysis.budget_impact.withdrawal_share_of_budget_bps
        )

    def test_non_requestable_post_state_is_none(self) -> None:
        ctx = _make_context(
            earned_amount_minor=0,
            policy_limit_minor=0,
            reserved_amount_minor=100000,
            paid_amount_minor=50000,
            available_amount_minor=0,
            max_requestable_amount_minor=0,
            eligible=False,
            can_request_withdrawal=False,
            eligibility_reasons=("NO_EMPLOYMENT",),
            minimum_withdrawal_minor=None,
            max_withdrawals_per_period=None,
        )
        analysis = analyze_withdrawal_from_context(ctx, 1000)

        self.assertFalse(analysis.requestability.requestable)
        self.assertIsNone(analysis.impact.remaining_available_amount_minor)
        self.assertIsNone(
            analysis.impact.remaining_max_requestable_amount_minor
        )
        # exposure_before is still a current-state read
        self.assertEqual(analysis.impact.exposure_before_minor, 150000)
        self.assertIsNone(analysis.impact.exposure_after_minor)
        self.assertIsNone(
            analysis.withdrawal_frequency.remaining_slots_after
        )

    # ------------------------------------------------------------------
    # HTTP integration tests
    # ------------------------------------------------------------------

    async def test_01_happy_path(self) -> None:
        token, user_id = await self._register_and_login("happy32@example.com")
        headers = {"Authorization": f"Bearer {token}"}
        await self._full_setup(token, user_id, "employer-h32")

        resp = await self.client.post(
            "/financial/withdrawal-analysis",
            headers=headers,
            params={"calculation_date": CALC_DATE.isoformat()},
            json={"amount_minor": 50000},
        )
        self.assertEqual(resp.status_code, 200, resp.text)
        analysis = WithdrawalAnalysis.model_validate(resp.json())

        self.assertTrue(analysis.snapshot_only)
        self.assertTrue(analysis.requestability.requestable)
        self.assertEqual(analysis.requestability.blocking_reasons, [])
        self.assertEqual(
            analysis.requestability.authoritative_eligibility_reasons, []
        )

        self.assertEqual(analysis.requested_amount_minor, 50000)
        self.assertEqual(analysis.current_state.earned_amount_minor, 500000)
        self.assertEqual(analysis.current_state.policy_limit_minor, 250000)
        self.assertEqual(analysis.current_state.available_amount_minor, 250000)
        self.assertEqual(
            analysis.current_state.max_requestable_amount_minor, 50000
        )

        # impact for a valid withdrawal
        self.assertEqual(
            analysis.impact.remaining_available_amount_minor, 200000
        )
        self.assertEqual(
            analysis.impact.remaining_max_requestable_amount_minor, 0
        )
        self.assertEqual(analysis.impact.exposure_before_minor, 0)
        self.assertEqual(analysis.impact.exposure_after_minor, 50000)
        self.assertEqual(
            analysis.impact.requested_share_of_earned_bps, 1000
        )
        self.assertEqual(
            analysis.impact.requested_share_of_policy_limit_bps, 2000
        )

        self.assertEqual(
            analysis.withdrawal_frequency.remaining_slots_before, 3
        )
        self.assertEqual(
            analysis.withdrawal_frequency.remaining_slots_after, 2
        )

    async def test_03_exceeds_max(self) -> None:
        token, user_id = await self._register_and_login("exceeds32@example.com")
        headers = {"Authorization": f"Bearer {token}"}
        await self._full_setup(token, user_id, "employer-ex32")

        resp = await self.client.post(
            "/financial/withdrawal-analysis",
            headers=headers,
            params={"calculation_date": CALC_DATE.isoformat()},
            json={"amount_minor": 50001},
        )
        self.assertEqual(resp.status_code, 200, resp.text)
        analysis = WithdrawalAnalysis.model_validate(resp.json())
        self.assertFalse(analysis.requestability.requestable)
        self.assertIn(
            "AMOUNT_EXCEEDS_MAX_REQUESTABLE",
            analysis.requestability.blocking_reasons,
        )
        self.assertNotIn(
            "AMOUNT_BELOW_MINIMUM", analysis.requestability.blocking_reasons
        )

    async def test_04_below_minimum(self) -> None:
        token, user_id = await self._register_and_login("below32@example.com")
        headers = {"Authorization": f"Bearer {token}"}
        await self._full_setup(token, user_id, "employer-b32")

        resp = await self.client.post(
            "/financial/withdrawal-analysis",
            headers=headers,
            params={"calculation_date": CALC_DATE.isoformat()},
            json={"amount_minor": 1000},
        )
        self.assertEqual(resp.status_code, 200, resp.text)
        analysis = WithdrawalAnalysis.model_validate(resp.json())
        self.assertFalse(analysis.requestability.requestable)
        self.assertIn(
            "AMOUNT_BELOW_MINIMUM", analysis.requestability.blocking_reasons
        )
        self.assertNotIn(
            "AMOUNT_EXCEEDS_MAX_REQUESTABLE",
            analysis.requestability.blocking_reasons,
        )

    async def test_05_ewa_ineligible(self) -> None:
        token, user_id = await self._register_and_login("inelig32@example.com")
        headers = {"Authorization": f"Bearer {token}"}
        # No employee / employment / policy -> fundamental ineligibility.
        resp = await self.client.post(
            "/financial/withdrawal-analysis",
            headers=headers,
            params={"calculation_date": CALC_DATE.isoformat()},
            json={"amount_minor": 50000},
        )
        self.assertEqual(resp.status_code, 200, resp.text)
        analysis = WithdrawalAnalysis.model_validate(resp.json())
        self.assertFalse(analysis.requestability.requestable)
        self.assertIn(
            "EWA_NOT_ELIGIBLE", analysis.requestability.blocking_reasons
        )
        self.assertIn(
            "NO_EMPLOYMENT",
            analysis.requestability.authoritative_eligibility_reasons,
        )
        # Must not also claim the withdrawal-limit code.
        self.assertNotIn(
            "WITHDRAWAL_LIMIT_REACHED",
            analysis.requestability.blocking_reasons,
        )

    async def test_06_can_request_false(self) -> None:
        token, user_id = await self._register_and_login("canreq32@example.com")
        headers = {"Authorization": f"Bearer {token}"}
        # A salary so low that earned accrual (and thus max requestable) falls
        # below the policy minimum withdrawal -> can_request_withdrawal False.
        async with self.sessions() as db:
            employer = Employer(id="employer-cr32", legal_name="CR Corp 32")
            db.add(employer)
            await db.commit()
            await self._add_policy(
                db,
                employer.id,
                minimum_withdrawal_minor=2000,
                maximum_withdrawal_minor=None,
            )
            await self._custom_salary_setup(db, user_id, employer.id, 100)
            await db.commit()

        resp = await self.client.post(
            "/financial/withdrawal-analysis",
            headers=headers,
            params={"calculation_date": CALC_DATE.isoformat()},
            json={"amount_minor": 50000},
        )
        self.assertEqual(resp.status_code, 200, resp.text)
        analysis = WithdrawalAnalysis.model_validate(resp.json())
        self.assertFalse(analysis.requestability.requestable)
        self.assertTrue(analysis.current_state.earned_amount_minor > 0)
        self.assertEqual(
            analysis.current_state.max_requestable_amount_minor, 0
        )
        self.assertIn(
            "WITHDRAWAL_NOT_ALLOWED", analysis.requestability.blocking_reasons
        )
        self.assertNotIn(
            "EWA_NOT_ELIGIBLE", analysis.requestability.blocking_reasons
        )

    async def test_07_withdrawal_limit_reached(self) -> None:
        token, user_id = await self._register_and_login("limit32@example.com")
        headers = {"Authorization": f"Bearer {token}"}

        async with self.sessions() as db:
            employer = Employer(id="employer-l32", legal_name="Limit Corp 32")
            db.add(employer)
            await db.commit()
            await self._add_policy(db, employer.id)
            await self._setup_complete(db, user_id, employer.id)
            for i in range(3):
                db.add(
                    WageAccessRequest(
                        id=f"lim32-{i}",
                        user_id=user_id,
                        amount_minor=10000,
                        status="pending",
                        pay_period_start=datetime(2026, 2, 1),
                        pay_period_end=datetime(2026, 2, 28),
                        created_at=datetime(2026, 2, 1),
                        updated_at=datetime(2026, 2, 1),
                    )
                )
            await db.commit()

        resp = await self.client.post(
            "/financial/withdrawal-analysis",
            headers=headers,
            params={"calculation_date": CALC_DATE.isoformat()},
            json={"amount_minor": 50000},
        )
        self.assertEqual(resp.status_code, 200, resp.text)
        analysis = WithdrawalAnalysis.model_validate(resp.json())
        self.assertFalse(analysis.requestability.requestable)
        self.assertIn(
            "WITHDRAWAL_LIMIT_REACHED", analysis.requestability.blocking_reasons
        )
        self.assertIn(
            "MAX_WITHDRAWALS_EXCEEDED",
            analysis.requestability.authoritative_eligibility_reasons,
        )
        self.assertEqual(
            analysis.withdrawal_frequency.remaining_slots_before, 0
        )
        # current_state still reflects the authoritative engine values
        self.assertEqual(
            analysis.current_state.reserved_amount_minor, 30000
        )

    async def test_13_transactions_goals_unchanged(self) -> None:
        token, user_id = await self._register_and_login("unch32@example.com")
        headers = {"Authorization": f"Bearer {token}"}
        await self._full_setup(token, user_id, "employer-unch32")

        async with self.sessions() as db:
            db.add(
                Transaction(
                    id="tx-unch-1",
                    user_id=user_id,
                    type="expense",
                    amount_minor=50000,
                    category="Rent",
                    merchant="Landlord",
                    description="Rent",
                    date="2026-02-01",
                )
            )
            db.add(
                Goal(
                    id="goal-unch-1",
                    user_id=user_id,
                    title="Reserve",
                    target_minor=100000,
                    current_minor=40000,
                    status="active",
                    progress_pct=40,
                )
            )
            db.add(
                Budget(
                    id="budget-unch-1",
                    user_id=user_id,
                    category="Food",
                    limit_minor=50000,
                    spent_minor=20000,
                    period="monthly",
                )
            )
            await db.commit()

        tx_before = await self._count_transactions(user_id)
        goals_before = await self._count_goals(user_id)
        budgets_before = await self._count_budgets(user_id)

        resp = await self.client.post(
            "/financial/withdrawal-analysis",
            headers=headers,
            params={"calculation_date": CALC_DATE.isoformat()},
            json={"amount_minor": 50000},
        )
        self.assertEqual(resp.status_code, 200, resp.text)

        self.assertEqual(await self._count_transactions(user_id), tx_before)
        self.assertEqual(await self._count_goals(user_id), goals_before)
        self.assertEqual(await self._count_budgets(user_id), budgets_before)

    async def test_14_no_wage_access_request_created(self) -> None:
        token, user_id = await self._register_and_login("nowar32@example.com")
        headers = {"Authorization": f"Bearer {token}"}
        await self._full_setup(token, user_id, "employer-nowar32")

        self.assertEqual(await self._count_wage_requests(user_id), 0)

        resp = await self.client.post(
            "/financial/withdrawal-analysis",
            headers=headers,
            params={"calculation_date": CALC_DATE.isoformat()},
            json={"amount_minor": 50000},
        )
        self.assertEqual(resp.status_code, 200, resp.text)

        self.assertEqual(await self._count_wage_requests(user_id), 0)

    async def test_15_repeated_analysis_no_capacity_change(self) -> None:
        token, user_id = await self._register_and_login("repeat32@example.com")
        headers = {"Authorization": f"Bearer {token}"}
        await self._full_setup(token, user_id, "employer-rep32")

        first = await self.client.post(
            "/financial/withdrawal-analysis",
            headers=headers,
            params={"calculation_date": CALC_DATE.isoformat()},
            json={"amount_minor": 50000},
        )
        second = await self.client.post(
            "/financial/withdrawal-analysis",
            headers=headers,
            params={"calculation_date": CALC_DATE.isoformat()},
            json={"amount_minor": 50000},
        )
        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)

        # Deterministic: identical payloads.
        self.assertEqual(first.json(), second.json())
        # No side effects.
        self.assertEqual(await self._count_wage_requests(user_id), 0)
        self.assertEqual(
            WithdrawalAnalysis.model_validate(first.json()).current_state,
            WithdrawalAnalysis.model_validate(second.json()).current_state,
        )

    async def test_16_user_isolation(self) -> None:
        token_a, user_a = await self._register_and_login(
            "iso_a32@example.com"
        )
        token_b, user_b = await self._register_and_login(
            "iso_b32@example.com"
        )
        headers_a = {"Authorization": f"Bearer {token_a}"}
        headers_b = {"Authorization": f"Bearer {token_b}"}

        async with self.sessions() as db:
            emp_a = Employer(id="employer-iso-a", legal_name="A Corp")
            emp_b = Employer(id="employer-iso-b", legal_name="B Corp")
            db.add(emp_a)
            db.add(emp_b)
            await db.commit()
            # User B has a distinct (lower) salary.
            await self._add_policy(db, emp_a.id)
            await self._add_policy(db, emp_b.id)
            await self._setup_complete(db, user_a, emp_a.id)
            ids_b = await self._custom_salary_setup(db, user_b, emp_b.id, 500000)
            await db.commit()

        resp_a = await self.client.post(
            "/financial/withdrawal-analysis",
            headers=headers_a,
            params={"calculation_date": CALC_DATE.isoformat()},
            json={"amount_minor": 10000},
        )
        resp_b = await self.client.post(
            "/financial/withdrawal-analysis",
            headers=headers_b,
            params={"calculation_date": CALC_DATE.isoformat()},
            json={"amount_minor": 10000},
        )
        self.assertEqual(resp_a.status_code, 200, resp_a.text)
        self.assertEqual(resp_b.status_code, 200, resp_b.text)
        analysis_a = WithdrawalAnalysis.model_validate(resp_a.json())
        analysis_b = WithdrawalAnalysis.model_validate(resp_b.json())

        self.assertNotEqual(
            analysis_a.current_state.earned_amount_minor,
            analysis_b.current_state.earned_amount_minor,
        )
        self.assertEqual(analysis_a.current_state.earned_amount_minor, 500000)
        self.assertEqual(analysis_b.current_state.earned_amount_minor, 250000)

    async def test_17_cross_tenant_isolation(self) -> None:
        token_a, user_a = await self._register_and_login(
            "ct_a32@example.com"
        )
        token_b, user_b = await self._register_and_login(
            "ct_b32@example.com"
        )
        headers_a = {"Authorization": f"Bearer {token_a}"}
        headers_b = {"Authorization": f"Bearer {token_b}"}

        async with self.sessions() as db:
            emp_a = Employer(id="employer-ct-a", legal_name="Tenant A")
            emp_b = Employer(id="employer-ct-b", legal_name="Tenant B")
            db.add(emp_a)
            db.add(emp_b)
            await db.commit()
            await self._add_policy(db, emp_a.id)
            await self._add_policy(db, emp_b.id)
            await self._setup_complete(db, user_a, emp_a.id)
            await self._setup_complete(db, user_b, emp_b.id)

            db.add(
                Transaction(
                    id="tx-ct-a",
                    user_id=user_a,
                    type="expense",
                    amount_minor=111111,
                    category="TenantA",
                    merchant="Tenant A",
                    description="Tenant A only",
                    date="2026-02-01",
                )
            )
            db.add(
                Budget(
                    id="budget-ct-a",
                    user_id=user_a,
                    category="Exclusive",
                    limit_minor=999999,
                    spent_minor=1,
                    period="monthly",
                )
            )
            await db.commit()

        resp_a = await self.client.post(
            "/financial/withdrawal-analysis",
            headers=headers_a,
            params={"calculation_date": CALC_DATE.isoformat()},
            json={"amount_minor": 50000},
        )
        resp_b = await self.client.post(
            "/financial/withdrawal-analysis",
            headers=headers_b,
            params={"calculation_date": CALC_DATE.isoformat()},
            json={"amount_minor": 50000},
        )
        self.assertEqual(resp_a.status_code, 200, resp_a.text)
        self.assertEqual(resp_b.status_code, 200, resp_b.text)

        analysis_a = WithdrawalAnalysis.model_validate(resp_a.json())
        analysis_b = WithdrawalAnalysis.model_validate(resp_b.json())

        # B has no budget -> unavailable; A has its own budget.
        self.assertTrue(analysis_a.budget_impact.available)
        self.assertFalse(analysis_b.budget_impact.available)
        self.assertEqual(analysis_a.budget_impact.total_budget_minor, 999999)
        self.assertIsNone(analysis_b.budget_impact.total_budget_minor)
        # A's transaction category never leaks into B's context.
            # (spending is not part of the withdrawal analysis output, so we
            # assert budget isolation as the financial-state discriminator.)

    async def test_18_zero_rejected(self) -> None:
        token, user_id = await self._register_and_login("zero32@example.com")
        headers = {"Authorization": f"Bearer {token}"}
        await self._full_setup(token, user_id, "employer-zero32")

        resp = await self.client.post(
            "/financial/withdrawal-analysis",
            headers=headers,
            json={"amount_minor": 0},
        )
        self.assertEqual(resp.status_code, 422)

    async def test_19_negative_rejected(self) -> None:
        token, user_id = await self._register_and_login("neg32@example.com")
        headers = {"Authorization": f"Bearer {token}"}
        await self._full_setup(token, user_id, "employer-neg32")

        resp = await self.client.post(
            "/financial/withdrawal-analysis",
            headers=headers,
            json={"amount_minor": -5},
        )
        self.assertEqual(resp.status_code, 422)

    async def test_20_float_rejected(self) -> None:
        token, user_id = await self._register_and_login("float32@example.com")
        headers = {"Authorization": f"Bearer {token}"}
        await self._full_setup(token, user_id, "employer-float32")

        resp = await self.client.post(
            "/financial/withdrawal-analysis",
            headers=headers,
            json={"amount_minor": 50.0},
        )
        self.assertEqual(resp.status_code, 422)

    async def test_21_sensitive_fields_excluded(self) -> None:
        token, user_id = await self._register_and_login("sens32@example.com")
        headers = {"Authorization": f"Bearer {token}"}
        await self._full_setup(token, user_id, "employer-sens32")

        resp = await self.client.post(
            "/financial/withdrawal-analysis",
            headers=headers,
            params={"calculation_date": CALC_DATE.isoformat()},
            json={"amount_minor": 50000},
        )
        self.assertEqual(resp.status_code, 200, resp.text)
        payload = resp.json()
        self.assertNotIn("hashed_password", payload)
        self.assertNotIn("access_token", payload)
        self.assertNotIn("refresh_token", payload)
        self.assertNotIn("_sa_instance_state", payload)

        forbidden = ["password", "token", "secret", "apikey", "authorization"]

        def check(obj: Any, path: str = "$") -> None:
            if isinstance(obj, dict):
                for k, v in obj.items():
                    norm = "".join(c for c in str(k).lower() if c.isalnum())
                    for f in forbidden:
                        self.assertNotIn(f, norm)
                    check(v, f"{path}.{k}")
            elif isinstance(obj, list):
                for i, v in enumerate(obj):
                    check(v, f"{path}[{i}]")

        check(payload)

    async def test_22_no_float_financial_output(self) -> None:
        token, user_id = await self._register_and_login("nofloat32@example.com")
        headers = {"Authorization": f"Bearer {token}"}
        await self._full_setup(token, user_id, "employer-nf32")

        resp = await self.client.post(
            "/financial/withdrawal-analysis",
            headers=headers,
            params={"calculation_date": CALC_DATE.isoformat()},
            json={"amount_minor": 50000},
        )
        self.assertEqual(resp.status_code, 200, resp.text)
        payload = resp.json()

        def has_float(obj: Any) -> bool:
            if isinstance(obj, float):
                return True
            if isinstance(obj, dict):
                return any(has_float(v) for v in obj.values())
            if isinstance(obj, list):
                return any(has_float(v) for v in obj)
            return False

        self.assertFalse(has_float(payload), "Float value present in response")

        analysis = WithdrawalAnalysis.model_validate(payload)
        money_fields = [
            analysis.current_state.earned_amount_minor,
            analysis.current_state.policy_limit_minor,
            analysis.current_state.reserved_amount_minor,
            analysis.current_state.paid_amount_minor,
            analysis.current_state.available_amount_minor,
            analysis.current_state.max_requestable_amount_minor,
            analysis.impact.requested_share_of_earned_bps,
            analysis.impact.requested_share_of_policy_limit_bps,
            analysis.impact.exposure_before_minor,
            analysis.impact.exposure_after_minor,
        ]
        for value in money_fields:
            self.assertTrue(value is None or isinstance(value, int))

    async def test_23_amount_equals_max_requestable(self) -> None:
        token, user_id = await self._register_and_login("maxeq32@example.com")
        headers = {"Authorization": f"Bearer {token}"}
        await self._full_setup(token, user_id, "employer-maxeq32")

        resp = await self.client.post(
            "/financial/withdrawal-analysis",
            headers=headers,
            params={"calculation_date": CALC_DATE.isoformat()},
            json={"amount_minor": 50000},
        )
        self.assertEqual(resp.status_code, 200, resp.text)
        analysis = WithdrawalAnalysis.model_validate(resp.json())
        self.assertTrue(analysis.requestability.requestable)
        self.assertEqual(
            analysis.impact.remaining_max_requestable_amount_minor, 0
        )

    async def test_24_amount_equals_minimum(self) -> None:
        token, user_id = await self._register_and_login("mineq32@example.com")
        headers = {"Authorization": f"Bearer {token}"}
        await self._full_setup(token, user_id, "employer-mineq32")

        resp = await self.client.post(
            "/financial/withdrawal-analysis",
            headers=headers,
            params={"calculation_date": CALC_DATE.isoformat()},
            json={"amount_minor": 2000},
        )
        self.assertEqual(resp.status_code, 200, resp.text)
        analysis = WithdrawalAnalysis.model_validate(resp.json())
        # amount == minimum_withdrawal_minor is requestable (not below).
        self.assertTrue(analysis.requestability.requestable)
        self.assertNotIn(
            "AMOUNT_BELOW_MINIMUM", analysis.requestability.blocking_reasons
        )

    async def test_25_calculation_date_determinism(self) -> None:
        token, user_id = await self._register_and_login("det32@example.com")
        headers = {"Authorization": f"Bearer {token}"}
        await self._full_setup(token, user_id, "employer-det32")

        resp1 = await self.client.post(
            "/financial/withdrawal-analysis",
            headers=headers,
            params={"calculation_date": CALC_DATE.isoformat()},
            json={"amount_minor": 50000},
        )
        resp2 = await self.client.post(
            "/financial/withdrawal-analysis",
            headers=headers,
            params={"calculation_date": CALC_DATE.isoformat()},
            json={"amount_minor": 50000},
        )
        self.assertEqual(resp1.status_code, 200, resp1.text)
        self.assertEqual(resp2.status_code, 200, resp2.text)
        self.assertEqual(resp1.json(), resp2.json())

        analysis = WithdrawalAnalysis.model_validate(resp1.json())
        # Deterministic earned/policy values tied to the fixed calculation date.
        self.assertEqual(analysis.current_state.earned_amount_minor, 500000)
        self.assertEqual(analysis.current_state.policy_limit_minor, 250000)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _custom_salary_setup(
        self, db, user_id: str, employer_id: str, monthly_salary_minor: int
    ) -> None:
        seq = getattr(self, "_seq", 0) + 1
        self._seq = seq
        suffix = f"-{seq}"
        employee = Employee(id=f"emp{suffix}", user_id=user_id, status="active")
        db.add(employee)
        employment = Employment(
            id=f"emp{suffix}-emp",
            employee_id=employee.id,
            employer_id=employer_id,
            status="active",
            start_date=datetime(2026, 1, 1),
            eligible_from=datetime(2026, 1, 1),
        )
        db.add(employment)
        salary = SalaryProfile(
            id=f"sal{suffix}",
            employment_id=employment.id,
            currency="USD",
            monthly_salary_amount_minor=monthly_salary_minor,
            pay_schedule="monthly",
            effective_from=datetime(2026, 1, 1),
            status="active",
        )
        db.add(salary)


if __name__ == "__main__":
    unittest.main()
