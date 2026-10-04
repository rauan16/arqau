"""Phase 3.1 Financial Context Builder Tests.

Covers:
A. Happy path
B. Exact authoritative EWA consistency with calculate_ewa()
C. User isolation
D. Withdrawal isolation
E. Withdrawal status aggregation
F. Paid total only includes paid requests
G. Empty real transaction dataset produces known zero, not fake data
H. Missing budget != zero budget
I. Missing goals != zero-value goals
J. Legitimate known-zero values remain zero
K. Missing core EWA state follows Phase 2 READ semantics
L. All money fields are integer / Optional integer, never float
M. Recent withdrawals limited to 10
N. Sensitive fields excluded
O. Cross-tenant isolation
"""

from __future__ import annotations

import os
import tempfile
import unittest
from datetime import date, datetime
from pathlib import Path
from typing import Any

import httpx

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
    WageAccessRequest,
)
from app.schemas.financial_context import FinancialContext
from app.services.ewa_engine import calculate_ewa

os.environ.setdefault("APP_ENV", "testing")
os.environ.setdefault("SECRET_KEY", "test-secret")
os.environ.setdefault("OPENAI_API_KEY", "test-key")

RECENT_WITHDRAWALS_LIMIT = 10


class Phase31FinancialContextTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        database_path = Path(self.temp_dir.name) / "fc.db"
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

    async def _register_and_login(self, email: str) -> tuple[str, str]:
        body = {"email": email, "password": "password123", "name": "Test"}
        resp = await self.client.post("/auth/register", json=body)
        self.assertEqual(resp.status_code, 200, resp.text)
        data = resp.json()
        token = data["access_token"]
        user_id = data["user_id"]
        login = await self.client.post(
            "/auth/login", json={"email": email, "password": "password123"}
        )
        self.assertEqual(login.status_code, 200)
        return token, user_id

    async def _setup_complete(
        self, db, user_id: str, employer_id: str
    ) -> dict:
        _seq = getattr(self, "_setup_seq", 0) + 1
        self._setup_seq = _seq
        suffix = f"-{_seq}" if _seq > 1 else ""
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

    async def _add_transactions(self, db, user_id: str) -> None:
        db.add(
            Transaction(
                id="tx-1",
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
            Transaction(
                id="tx-2",
                user_id=user_id,
                type="expense",
                amount_minor=30000,
                category="Food",
                merchant="Grocery",
                description="Groceries",
                date="2026-02-02",
            )
        )
        db.add(
            Transaction(
                id="tx-3",
                user_id=user_id,
                type="income",
                amount_minor=1000000,
                category="Salary",
                merchant="Employer",
                description="Salary",
                date="2026-02-01",
            )
        )
        await db.commit()

    async def _add_withdrawal_requests(self, db, user_id: str) -> None:
        statuses = [
            ("pending", "req-pending"),
            ("approved", "req-approved"),
            ("paid", "req-paid"),
            ("rejected", "req-rejected"),
            ("cancelled", "req-cancelled"),
        ]
        for status, rid in statuses:
            db.add(
                WageAccessRequest(
                    id=rid,
                    user_id=user_id,
                    amount_minor=10000,
                    status=status,
                    created_at=datetime(2026, 2, 1),
                    updated_at=datetime(2026, 2, 1),
                )
            )
        await db.commit()

    # ------------------------------------------------------------------
    # A. Happy path
    # ------------------------------------------------------------------

    async def test_happy_path(self) -> None:
        token, user_id = await self._register_and_login("happy@example.com")
        headers = {"Authorization": f"Bearer {token}"}

        async with self.sessions() as db:
            employer = Employer(id="employer-1", legal_name="Test Corp")
            db.add(employer)
            await db.commit()
            db.add(
                EwaPolicy(
                    id="policy-1",
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
            ids = await self._setup_complete(db, user_id, employer.id)
            await self._add_transactions(db, user_id)
            db.add(
                Budget(
                    id="budget-1",
                    user_id=user_id,
                    category="Food",
                    limit_minor=50000,
                    spent_minor=20000,
                    period="monthly",
                )
            )
            db.add(
                Goal(
                    id="goal-1",
                    user_id=user_id,
                    title="Reserve",
                    target_minor=100000,
                    current_minor=40000,
                    status="active",
                    progress_pct=40,
                )
            )
            await self._add_withdrawal_requests(db, user_id)
            await db.commit()

        calc_date = date(2026, 2, 15)
        resp = await self.client.get(
            "/financial/context",
            headers=headers,
            params={"calculation_date": calc_date.isoformat()},
        )
        self.assertEqual(resp.status_code, 200, resp.text)
        ctx = FinancialContext.model_validate(resp.json())

        self.assertEqual(ctx.user_id, user_id)
        self.assertIsNotNone(ctx.generated_at)
        self.assertEqual(ctx.calculation_date, calc_date)

        self.assertEqual(ctx.employment.employment_id, ids["employment_id"])
        self.assertEqual(ctx.employment.employer_id, "employer-1")
        self.assertEqual(ctx.employment.employer_name, "Test Corp")
        self.assertEqual(ctx.employment.employment_status, "active")
        self.assertEqual(ctx.income.salary_amount_minor, 1000000)
        self.assertEqual(ctx.income.currency, "USD")

        self.assertTrue(ctx.spending.available)
        self.assertEqual(ctx.spending.total_spending_minor, 80000)
        self.assertEqual(ctx.spending.transaction_count, 2)
        self.assertEqual(len(ctx.spending.category_breakdown), 2)

        self.assertTrue(ctx.budget.available)
        self.assertEqual(ctx.budget.total_budget_minor, 50000)
        self.assertEqual(ctx.budget.spent_minor, 20000)
        self.assertEqual(ctx.budget.remaining_minor, 30000)

        self.assertTrue(ctx.goals.available)
        self.assertEqual(ctx.goals.active_goals_count, 1)
        self.assertEqual(ctx.goals.total_target_minor, 100000)
        self.assertEqual(ctx.goals.total_saved_minor, 40000)
        self.assertEqual(len(ctx.goals.goals), 1)

        self.assertTrue(ctx.data_quality.has_salary_profile)
        self.assertTrue(ctx.data_quality.has_ewa_policy)
        self.assertTrue(ctx.data_quality.has_transactions)
        self.assertTrue(ctx.data_quality.has_budget)
        self.assertTrue(ctx.data_quality.has_goals)
        self.assertEqual(ctx.data_quality.missing_data, [])

    # ------------------------------------------------------------------
    # B. Exact authoritative EWA consistency
    # ------------------------------------------------------------------

    async def test_ewa_exactly_matches_calculate_ewa(self) -> None:
        token, user_id = await self._register_and_login("ewa_consistency@example.com")
        headers = {"Authorization": f"Bearer {token}"}

        calc_date = date(2026, 2, 15)

        async with self.sessions() as db:
            employer = Employer(id="employer-ewa", legal_name="EWA Corp")
            db.add(employer)
            await db.commit()
            await self._setup_complete(db, user_id, employer.id)
            await db.commit()

        async with self.sessions() as db:
            calc = await calculate_ewa(db, user_id, calc_date)

        resp = await self.client.get(
            "/financial/context",
            headers=headers,
            params={"calculation_date": calc_date.isoformat()},
        )
        self.assertEqual(resp.status_code, 200, resp.text)
        ctx = FinancialContext.model_validate(resp.json())

        ewa = ctx.ewa
        self.assertEqual(ewa.earned_amount_minor, calc.earned_amount_minor)
        self.assertEqual(ewa.policy_limit_minor, calc.policy_limit_minor)
        self.assertEqual(ewa.reserved_amount_minor, calc.reserved_amount_minor)
        self.assertEqual(ewa.paid_amount_minor, calc.paid_amount_minor)
        self.assertEqual(ewa.available_amount_minor, calc.available_amount_minor)
        self.assertEqual(
            ewa.max_requestable_amount_minor, calc.max_requestable_amount_minor
        )
        self.assertEqual(ewa.eligible, calc.eligible)
        self.assertEqual(ewa.eligibility_reasons, list(calc.eligibility_reasons))
        self.assertEqual(ewa.can_request_withdrawal, calc.can_request_withdrawal)
        self.assertEqual(ewa.max_withdrawals_per_period, calc.max_withdrawals_per_period)
        self.assertEqual(ewa.withdrawals_this_period, calc.withdrawals_this_period)
        if calc.minimum_withdrawal_minor is not None:
            self.assertEqual(ewa.minimum_withdrawal_minor, calc.minimum_withdrawal_minor)
        if calc.maximum_withdrawal_minor is not None:
            self.assertEqual(ewa.maximum_withdrawal_minor, calc.maximum_withdrawal_minor)

    # ------------------------------------------------------------------
    # C. User isolation
    # ------------------------------------------------------------------

    async def test_user_isolation(self) -> None:
        token_a, user_a = await self._register_and_login("user_a@example.com")
        token_b, user_b = await self._register_and_login("user_b@example.com")
        headers_a = {"Authorization": f"Bearer {token_a}"}
        headers_b = {"Authorization": f"Bearer {token_b}"}

        async with self.sessions() as db:
            emp_a = Employer(id="employer-a", legal_name="Employer A")
            emp_b = Employer(id="employer-b", legal_name="Employer B")
            db.add(emp_a)
            db.add(emp_b)
            await db.commit()

            await self._setup_complete(db, user_a, emp_a.id)
            await self._setup_complete(db, user_b, emp_b.id)

            db.add(
                Transaction(
                    id="tx-a-secret",
                    user_id=user_a,
                    type="expense",
                    amount_minor=999999,
                    category="Secret",
                    merchant="Secret",
                    description="User A only",
                    date="2026-02-01",
                )
            )
            await db.commit()

        resp_a = await self.client.get("/financial/context", headers=headers_a)
        self.assertEqual(resp_a.status_code, 200)
        ctx_a = FinancialContext.model_validate(resp_a.json())

        resp_b = await self.client.get("/financial/context", headers=headers_b)
        self.assertEqual(resp_b.status_code, 200)
        ctx_b = FinancialContext.model_validate(resp_b.json())

        self.assertEqual(ctx_a.user_id, user_a)
        self.assertEqual(ctx_b.user_id, user_b)
        self.assertNotEqual(ctx_a.user_id, ctx_b.user_id)

        a_categories = {c.category for c in ctx_a.spending.category_breakdown}
        b_categories = {c.category for c in ctx_b.spending.category_breakdown}
        self.assertNotIn("Secret", b_categories)
        self.assertIn("Secret", a_categories)

    # ------------------------------------------------------------------
    # D. Withdrawal isolation
    # ------------------------------------------------------------------

    async def test_withdrawal_isolation(self) -> None:
        token_a, user_a = await self._register_and_login("wd_a@example.com")
        token_b, user_b = await self._register_and_login("wd_b@example.com")
        headers_a = {"Authorization": f"Bearer {token_a}"}
        headers_b = {"Authorization": f"Bearer {token_b}"}

        async with self.sessions() as db:
            emp_a = Employer(id="employer-wd-a", legal_name="Employer A")
            emp_b = Employer(id="employer-wd-b", legal_name="Employer B")
            db.add(emp_a)
            db.add(emp_b)
            await db.commit()

            await self._setup_complete(db, user_a, emp_a.id)
            await self._setup_complete(db, user_b, emp_b.id)

            for i in range(3):
                db.add(
                    WageAccessRequest(
                        id=f"wd-a-{i}",
                        user_id=user_a,
                        amount_minor=10000 + i,
                        status="pending",
                        created_at=datetime(2026, 2, 1),
                    )
                )
            for i in range(3):
                db.add(
                    WageAccessRequest(
                        id=f"wd-b-{i}",
                        user_id=user_b,
                        amount_minor=50000 + i,
                        status="pending",
                        created_at=datetime(2026, 2, 1),
                    )
                )
            await db.commit()

        resp_a = await self.client.get("/financial/context", headers=headers_a)
        ctx_a = FinancialContext.model_validate(resp_a.json())

        resp_b = await self.client.get("/financial/context", headers=headers_b)
        ctx_b = FinancialContext.model_validate(resp_b.json())

        a_recent_ids = {r.id for r in ctx_a.withdrawal_history.recent_requests}
        b_recent_ids = {r.id for r in ctx_b.withdrawal_history.recent_requests}
        for i in range(3):
            self.assertIn(f"wd-a-{i}", a_recent_ids)
            self.assertNotIn(f"wd-b-{i}", a_recent_ids)
            self.assertIn(f"wd-b-{i}", b_recent_ids)

    # ------------------------------------------------------------------
    # E. Withdrawal status aggregation
    # ------------------------------------------------------------------

    async def test_withdrawal_status_aggregation(self) -> None:
        token, user_id = await self._register_and_login("agg@example.com")
        headers = {"Authorization": f"Bearer {token}"}

        async with self.sessions() as db:
            employer = Employer(id="employer-agg", legal_name="Agg Corp")
            db.add(employer)
            await db.commit()
            await self._setup_complete(db, user_id, employer.id)
            await self._add_withdrawal_requests(db, user_id)
            await db.commit()

        resp = await self.client.get("/financial/context", headers=headers)
        ctx = FinancialContext.model_validate(resp.json())
        wh = ctx.withdrawal_history

        self.assertEqual(wh.total_requests, 5)
        self.assertEqual(wh.pending_count, 1)
        self.assertEqual(wh.approved_count, 1)
        self.assertEqual(wh.paid_count, 1)
        self.assertEqual(wh.rejected_count, 1)
        self.assertEqual(wh.cancelled_count, 1)

    # ------------------------------------------------------------------
    # F. Paid total only includes paid requests
    # ------------------------------------------------------------------

    async def test_paid_total_only_includes_paid_requests(self) -> None:
        token, user_id = await self._register_and_login("paid@example.com")
        headers = {"Authorization": f"Bearer {token}"}

        async with self.sessions() as db:
            employer = Employer(id="employer-paid", legal_name="Paid Corp")
            db.add(employer)
            await db.commit()
            await self._setup_complete(db, user_id, employer.id)

            db.add(
                WageAccessRequest(
                    id="p-1",
                    user_id=user_id,
                    amount_minor=10000,
                    status="paid",
                    created_at=datetime(2026, 2, 1),
                )
            )
            db.add(
                WageAccessRequest(
                    id="p-2",
                    user_id=user_id,
                    amount_minor=20000,
                    status="pending",
                    created_at=datetime(2026, 2, 1),
                )
            )
            db.add(
                WageAccessRequest(
                    id="p-3",
                    user_id=user_id,
                    amount_minor=30000,
                    status="approved",
                    created_at=datetime(2026, 2, 1),
                )
            )
            await db.commit()

        resp = await self.client.get("/financial/context", headers=headers)
        ctx = FinancialContext.model_validate(resp.json())
        wh = ctx.withdrawal_history

        self.assertEqual(wh.total_requests, 3)
        self.assertEqual(wh.requested_amount_minor, 60000)
        self.assertEqual(wh.paid_amount_minor, 10000)

    # ------------------------------------------------------------------
    # G. Empty real transaction dataset produces known zero
    # ------------------------------------------------------------------

    async def test_empty_transactions_known_zero(self) -> None:
        token, user_id = await self._register_and_login("empty@example.com")
        headers = {"Authorization": f"Bearer {token}"}

        async with self.sessions() as db:
            employer = Employer(id="employer-empty", legal_name="Empty Corp")
            db.add(employer)
            await db.commit()
            await self._setup_complete(db, user_id, employer.id)
            await db.commit()

        resp = await self.client.get("/financial/context", headers=headers)
        ctx = FinancialContext.model_validate(resp.json())

        self.assertTrue(ctx.data_quality.has_transactions)
        self.assertTrue(ctx.spending.available)
        self.assertEqual(ctx.spending.total_spending_minor, 0)
        self.assertEqual(ctx.spending.transaction_count, 0)
        self.assertEqual(ctx.spending.category_breakdown, [])
        self.assertEqual(ctx.spending.essential_spending_minor, None)
        self.assertEqual(ctx.spending.discretionary_spending_minor, None)

    # ------------------------------------------------------------------
    # H. Missing budget != zero budget
    # ------------------------------------------------------------------

    async def test_missing_budget_not_zero(self) -> None:
        token, user_id = await self._register_and_login("nobudget@example.com")
        headers = {"Authorization": f"Bearer {token}"}

        async with self.sessions() as db:
            employer = Employer(id="employer-nb", legal_name="No Budget Corp")
            db.add(employer)
            await db.commit()
            await self._setup_complete(db, user_id, employer.id)
            await db.commit()

        resp = await self.client.get("/financial/context", headers=headers)
        ctx = FinancialContext.model_validate(resp.json())

        self.assertFalse(ctx.data_quality.has_budget)
        self.assertFalse(ctx.budget.available)
        self.assertEqual(ctx.budget.total_budget_minor, None)
        self.assertEqual(ctx.budget.spent_minor, None)
        self.assertEqual(ctx.budget.remaining_minor, None)

    # ------------------------------------------------------------------
    # I. Missing goals != zero-value goals
    # ------------------------------------------------------------------

    async def test_missing_goals_not_zero(self) -> None:
        token, user_id = await self._register_and_login("nogoals@example.com")
        headers = {"Authorization": f"Bearer {token}"}

        async with self.sessions() as db:
            employer = Employer(id="employer-ng", legal_name="No Goals Corp")
            db.add(employer)
            await db.commit()
            await self._setup_complete(db, user_id, employer.id)
            await db.commit()

        resp = await self.client.get("/financial/context", headers=headers)
        ctx = FinancialContext.model_validate(resp.json())

        self.assertFalse(ctx.data_quality.has_goals)
        self.assertFalse(ctx.goals.available)
        self.assertEqual(ctx.goals.active_goals_count, None)
        self.assertEqual(ctx.goals.total_target_minor, None)
        self.assertEqual(ctx.goals.total_saved_minor, None)
        self.assertEqual(ctx.goals.goals, [])

    # ------------------------------------------------------------------
    # J. Legitimate known-zero values remain zero
    # ------------------------------------------------------------------

    async def test_legitimate_known_zero(self) -> None:
        token, user_id = await self._register_and_login("zero@example.com")
        headers = {"Authorization": f"Bearer {token}"}

        async with self.sessions() as db:
            employer = Employer(id="employer-zero", legal_name="Zero Corp")
            db.add(employer)
            await db.commit()
            await self._setup_complete(db, user_id, employer.id)

            db.add(
                Budget(
                    id="budget-zero",
                    user_id=user_id,
                    category="Empty",
                    limit_minor=0,
                    spent_minor=0,
                    period="monthly",
                )
            )
            db.add(
                Goal(
                    id="goal-zero",
                    user_id=user_id,
                    title="Nothing",
                    target_minor=0,
                    current_minor=0,
                    status="active",
                    progress_pct=0,
                )
            )
            await db.commit()

        resp = await self.client.get("/financial/context", headers=headers)
        ctx = FinancialContext.model_validate(resp.json())

        self.assertTrue(ctx.data_quality.has_budget)
        self.assertTrue(ctx.budget.available)
        self.assertEqual(ctx.budget.total_budget_minor, 0)
        self.assertEqual(ctx.budget.spent_minor, 0)
        self.assertEqual(ctx.budget.remaining_minor, 0)

        self.assertTrue(ctx.data_quality.has_goals)
        self.assertTrue(ctx.goals.available)
        self.assertEqual(ctx.goals.active_goals_count, 1)
        self.assertEqual(ctx.goals.total_target_minor, 0)
        self.assertEqual(ctx.goals.total_saved_minor, 0)

    # ------------------------------------------------------------------
    # K. Missing core EWA state follows Phase 2 READ semantics
    # ------------------------------------------------------------------

    async def test_missing_salary_profile_ineligible(self) -> None:
        token, user_id = await self._register_and_login("nosalary@example.com")
        headers = {"Authorization": f"Bearer {token}"}

        async with self.sessions() as db:
            employer = Employer(id="employer-ns", legal_name="No Salary Corp")
            db.add(employer)
            await db.commit()
            employee = Employee(id="emp-ns", user_id=user_id, status="active")
            db.add(employee)
            employment = Employment(
                id="emp-ns-emp",
                employee_id=employee.id,
                employer_id=employer.id,
                status="active",
                start_date=datetime(2026, 1, 1),
            )
            db.add(employment)
            await db.commit()

        calc_date = date(2026, 2, 15)
        resp = await self.client.get(
            "/financial/context",
            headers=headers,
            params={"calculation_date": calc_date.isoformat()},
        )
        self.assertEqual(resp.status_code, 200, resp.text)
        ctx = FinancialContext.model_validate(resp.json())

        self.assertFalse(ctx.ewa.eligible)
        self.assertEqual(ctx.ewa.salary_amount_minor, 0)
        self.assertEqual(ctx.ewa.earned_amount_minor, 0)
        self.assertEqual(ctx.ewa.available_amount_minor, 0)
        self.assertIn("NO_ACTIVE_SALARY_PROFILE", ctx.ewa.eligibility_reasons)
        self.assertEqual(ctx.income.salary_amount_minor, None)
        self.assertEqual(ctx.income.currency, None)
        self.assertFalse(ctx.data_quality.has_salary_profile)

    # ------------------------------------------------------------------
    # L. Money fields never floats
    # ------------------------------------------------------------------

    async def test_money_fields_never_floats(self) -> None:
        token, user_id = await self._register_and_login("moneytypes@example.com")
        headers = {"Authorization": f"Bearer {token}"}

        async with self.sessions() as db:
            employer = Employer(id="employer-mt", legal_name="Money Corp")
            db.add(employer)
            await db.commit()
            await self._setup_complete(db, user_id, employer.id)
            await db.commit()

        resp = await self.client.get("/financial/context", headers=headers)
        ctx = FinancialContext.model_validate(resp.json())

        def assert_no_floats(obj: Any, path: str = "$") -> None:
            if isinstance(obj, float):
                self.fail(f"Float found at {path}: {obj}")
            if isinstance(obj, dict):
                for k, v in obj.items():
                    assert_no_floats(v, f"{path}.{k}")
            elif isinstance(obj, list):
                for i, v in enumerate(obj):
                    assert_no_floats(v, f"{path}[{i}]")

        assert_no_floats(ctx.model_dump())

        money_fields = [
            ("ewa", "earned_amount_minor"),
            ("ewa", "policy_limit_minor"),
            ("ewa", "reserved_amount_minor"),
            ("ewa", "paid_amount_minor"),
            ("ewa", "available_amount_minor"),
            ("ewa", "max_requestable_amount_minor"),
            ("withdrawal_history", "total_requests"),
            ("withdrawal_history", "requested_amount_minor"),
            ("withdrawal_history", "paid_amount_minor"),
            ("spending", "total_spending_minor"),
            ("spending", "transaction_count"),
            ("budget", "total_budget_minor"),
            ("budget", "spent_minor"),
            ("budget", "remaining_minor"),
            ("goals", "active_goals_count"),
            ("goals", "total_target_minor"),
            ("goals", "total_saved_minor"),
        ]
        for section, field in money_fields:
            value = getattr(getattr(ctx, section), field)
            if value is not None:
                self.assertIsInstance(
                    value, int,
                    f"{section}.{field} is {type(value).__name__}, expected int",
                )

    # ------------------------------------------------------------------
    # M. Recent withdrawals limited to 10
    # ------------------------------------------------------------------

    async def test_recent_withdrawals_limited_to_10(self) -> None:
        token, user_id = await self._register_and_login("limit10@example.com")
        headers = {"Authorization": f"Bearer {token}"}

        async with self.sessions() as db:
            employer = Employer(id="employer-l10", legal_name="Limit Corp")
            db.add(employer)
            await db.commit()
            await self._setup_complete(db, user_id, employer.id)

            for i in range(12):
                db.add(
                    WageAccessRequest(
                        id=f"limit10-{i}",
                        user_id=user_id,
                        amount_minor=10000,
                        status="pending",
                        created_at=datetime(2026, 2, 1),
                    )
                )
            await db.commit()

        resp = await self.client.get("/financial/context", headers=headers)
        ctx = FinancialContext.model_validate(resp.json())
        recent = ctx.withdrawal_history.recent_requests

        self.assertEqual(ctx.withdrawal_history.total_requests, 12)
        self.assertLessEqual(len(recent), RECENT_WITHDRAWALS_LIMIT)
        self.assertEqual(len(recent), 10)

        for r in recent:
            self.assertTrue(r.id.startswith("limit10-"))

    # ------------------------------------------------------------------
    # N. Sensitive fields excluded
    # ------------------------------------------------------------------

    async def test_sensitive_fields_excluded(self) -> None:
        token, user_id = await self._register_and_login("sensitive@example.com")
        headers = {"Authorization": f"Bearer {token}"}

        async with self.sessions() as db:
            employer = Employer(id="employer-s", legal_name="Sensitive Corp")
            db.add(employer)
            await db.commit()
            await self._setup_complete(db, user_id, employer.id)
            await db.commit()

        resp = await self.client.get("/financial/context", headers=headers)
        ctx = FinancialContext.model_validate(resp.json())
        data = ctx.model_dump()

        forbidden_substrings = [
            "password",
            "token",
            "secret",
            "apikey",
            "authorization",
            "cookie",
            "hashed",
        ]

        def check_no_sensitive(obj: Any, path: str = "$") -> None:
            if isinstance(obj, dict):
                for k, v in obj.items():
                    normalized = "".join(
                        c for c in str(k).lower() if c.isalnum()
                    )
                    for forbidden in forbidden_substrings:
                        self.assertNotIn(
                            forbidden, normalized,
                            f"Sensitive key {k} at {path}",
                        )
                    check_no_sensitive(v, f"{path}.{k}")
            elif isinstance(obj, list):
                for i, v in enumerate(obj):
                    check_no_sensitive(v, f"{path}[{i}]")

        check_no_sensitive(data)

        self.assertNotIn("hashed_password", data)
        self.assertNotIn("access_token", data)
        self.assertNotIn("refresh_token", data)
        self.assertNotIn("_sa_instance_state", data)

    # ------------------------------------------------------------------
    # O. Cross-tenant isolation
    # ------------------------------------------------------------------

    async def test_cross_tenant_isolation(self) -> None:
        token_a, user_a = await self._register_and_login("tenant_a@example.com")
        token_b, user_b = await self._register_and_login("tenant_b@example.com")
        headers_a = {"Authorization": f"Bearer {token_a}"}
        headers_b = {"Authorization": f"Bearer {token_b}"}

        async with self.sessions() as db:
            employer_a = Employer(id="tenant-a", legal_name="Tenant A")
            employer_b = Employer(id="tenant-b", legal_name="Tenant B")
            db.add(employer_a)
            db.add(employer_b)
            await db.commit()

            await self._setup_complete(db, user_a, employer_a.id)
            await self._setup_complete(db, user_b, employer_b.id)

            db.add(
                Transaction(
                    id="tx-tenant-a",
                    user_id=user_a,
                    type="expense",
                    amount_minor=111111,
                    category="TenantA",
                    merchant="Tenant A",
                    description="Tenant A only",
                    date="2026-02-01",
                )
            )
            await db.commit()

        resp_a = await self.client.get("/financial/context", headers=headers_a)
        ctx_a = FinancialContext.model_validate(resp_a.json())

        resp_b = await self.client.get("/financial/context", headers=headers_b)
        ctx_b = FinancialContext.model_validate(resp_b.json())

        self.assertEqual(ctx_a.employment.employer_id, "tenant-a")
        self.assertEqual(ctx_b.employment.employer_id, "tenant-b")

        self.assertNotIn("Tenant B", {ctx_a.employment.employer_name})
        self.assertNotIn("Tenant A", {ctx_b.employment.employer_name})

        a_cats = {c.category for c in ctx_a.spending.category_breakdown}
        b_cats = {c.category for c in ctx_b.spending.category_breakdown}
        self.assertIn("TenantA", a_cats)
        self.assertNotIn("TenantA", b_cats)


if __name__ == "__main__":
    unittest.main()
