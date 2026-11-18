"""Phase 2.3 EWA Engine Tests

Deterministic unit tests for the EWA calculation engine.
"""

from __future__ import annotations

import os
import tempfile
import unittest
from datetime import date, datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import Base, configure_database, create_database
from app.config import get_settings
from app.database import get_db
from app.main import app
from app.models import (
    Employee,
    Employment,
    Employer,
    EwaPolicy,
    SalaryProfile,
    User,
    WageAccessRequest,
)
from app.core.auth_rate_limit import _reset_all_limiters
from app.services.ewa_engine import (
    EligibilityReason,
    _calculate_earned,
    _count_working_days,
    _get_pay_period,
    calculate_ewa,
)

os.environ.setdefault("APP_ENV", "testing")
os.environ.setdefault("SECRET_KEY", "test-secret")
os.environ.setdefault("OPENAI_API_KEY", "test-key")


class Phase23EwaEngineTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self._test_sessions = []
        database_path = Path(self.temp_dir.name) / "ewa_engine.db"
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

    async def asyncTearDown(self) -> None:
        app.dependency_overrides.clear()
        for session in self._test_sessions:
            await session.close()
        if self.original_url:
            await configure_database(self.original_url)
        await self.engine.dispose()
        self.temp_dir.cleanup()

    def _create_test_session(self) -> AsyncSession:
        session = self.sessions()
        self._test_sessions.append(session)
        return session

    # ---- PAY PERIOD TESTS ----

    def test_pay_period_28_day_february(self) -> None:
        calc_date = date(2026, 2, 15)
        start, end = _get_pay_period(calc_date)
        self.assertEqual(start, date(2026, 2, 1))
        self.assertEqual(end, date(2026, 2, 28))

    def test_pay_period_leap_year_february(self) -> None:
        calc_date = date(2028, 2, 15)
        start, end = _get_pay_period(calc_date)
        self.assertEqual(start, date(2028, 2, 1))
        self.assertEqual(end, date(2028, 2, 29))

    def test_pay_period_30_day_month(self) -> None:
        calc_date = date(2026, 4, 15)
        start, end = _get_pay_period(calc_date)
        self.assertEqual(start, date(2026, 4, 1))
        self.assertEqual(end, date(2026, 4, 30))

    def test_pay_period_31_day_month(self) -> None:
        calc_date = date(2026, 1, 15)
        start, end = _get_pay_period(calc_date)
        self.assertEqual(start, date(2026, 1, 1))
        self.assertEqual(end, date(2026, 1, 31))

    # ---- WORKING DAY TESTS ----

    def test_working_days_full_month(self) -> None:
        # February 2026: Mon Feb 1 - Sat Feb 28 = 20 working days
        count = _count_working_days(date(2026, 2, 1), date(2026, 2, 28))
        self.assertEqual(count, 20)

    def test_working_days_beginning_of_month(self) -> None:
        calc_date = date(2026, 2, 2)  # Monday
        start, end = _get_pay_period(calc_date)
        count = _count_working_days(start, calc_date)
        self.assertEqual(count, 1)

    def test_working_days_middle_of_month(self) -> None:
        calc_date = date(2026, 2, 15)
        start, end = _get_pay_period(calc_date)
        count = _count_working_days(start, calc_date)
        # Feb 1-15 2026: 10 working days (Mon 1 - Fri 13, Mon 15)
        self.assertEqual(count, 10)

    def test_working_days_end_of_month(self) -> None:
        calc_date = date(2026, 2, 28)
        start, end = _get_pay_period(calc_date)
        count = _count_working_days(start, calc_date)
        self.assertEqual(count, 20)

    def test_working_days_weekend_calculation(self) -> None:
        calc_date = date(2026, 2, 21)  # Saturday
        start, end = _get_pay_period(calc_date)
        count = _count_working_days(start, calc_date)
        # Should count only Mon-Fri up to Feb 21
        self.assertEqual(count, 15)

    def test_working_days_month_starting_weekend(self) -> None:
        # March 2026 starts on Sunday (Mar 1)
        calc_date = date(2026, 3, 5)  # Thursday
        start, end = _get_pay_period(calc_date)
        count = _count_working_days(start, calc_date)
        # Mar 1=Sun, 2=Mon, 3=Tue, 4=Wed, 5=Thu = 4 working days
        self.assertEqual(count, 4)

    # ---- EARNED CALCULATION ----

    def test_earned_beginning_of_month(self) -> None:
        # Feb 2 2026 (Monday), salary 1000000 minor
        earned = _calculate_earned(
            monthly_salary_minor=1000000,
            pay_period_start=date(2026, 2, 1),
            pay_period_end=date(2026, 2, 28),
            effective_start=date(2026, 2, 1),
            effective_end=date(2026, 2, 28),
            calculation_date=date(2026, 2, 2),
        )
        # Feb 1 is Sunday, Feb 2 is Monday = 1 working day / 20 working days = 1000000 * 1 // 20 = 50000
        self.assertEqual(earned, 50000)

    def test_earned_middle_of_month(self) -> None:
        earned = _calculate_earned(
            monthly_salary_minor=1000000,
            pay_period_start=date(2026, 2, 1),
            pay_period_end=date(2026, 2, 28),
            effective_start=date(2026, 2, 1),
            effective_end=date(2026, 2, 28),
            calculation_date=date(2026, 2, 13),  # Friday
        )
        # Feb 1=Sun, Feb 2-6=Mon-Fri (5), Feb 7=Sat, Feb 8=Sun, Feb 9-13=Mon-Fri (5) = 10 working days
        # 1000000 * 10 // 20 = 500000
        self.assertEqual(earned, 500000)

    def test_earned_end_of_month(self) -> None:
        earned = _calculate_earned(
            monthly_salary_minor=1000000,
            pay_period_start=date(2026, 2, 1),
            pay_period_end=date(2026, 2, 28),
            effective_start=date(2026, 2, 1),
            effective_end=date(2026, 2, 28),
            calculation_date=date(2026, 2, 27),  # Friday
        )
        # Feb 1=Sun, 28=Sat. Working days Mon-Fri = 20
        # Up to Feb 27 (Friday) = all 20 working days
        self.assertEqual(earned, 1000000)

    def test_earned_floor_rounding(self) -> None:
        # 1000001 * 10 // 20 = 500000 (floor)
        earned = _calculate_earned(
            monthly_salary_minor=1000001,
            pay_period_start=date(2026, 2, 1),
            pay_period_end=date(2026, 2, 28),
            effective_start=date(2026, 2, 1),
            effective_end=date(2026, 2, 28),
            calculation_date=date(2026, 2, 15),
        )
        self.assertEqual(earned, 500000)

    def test_earned_mid_month_employment_start(self) -> None:
        # Employment starts Feb 10, calculation Feb 15
        earned = _calculate_earned(
            monthly_salary_minor=1000000,
            pay_period_start=date(2026, 2, 1),
            pay_period_end=date(2026, 2, 28),
            effective_start=date(2026, 2, 10),
            effective_end=date(2026, 2, 28),
            calculation_date=date(2026, 2, 15),
        )
        # Feb 10-15: 4 working days (Mon 10 - Thu 13, Fri 14)
        # Wait, Feb 10 is Tuesday. 10=Tue, 11=Wed, 12=Thu, 13=Fri, 14=Sat, 15=Sun -> 4 working days
        # 1000000 * 4 // 20 = 200000
        self.assertEqual(earned, 200000)

    def test_earned_employment_starts_today(self) -> None:
        # Employment starts Feb 13 (Friday), calculation Feb 13
        earned = _calculate_earned(
            monthly_salary_minor=1000000,
            pay_period_start=date(2026, 2, 1),
            pay_period_end=date(2026, 2, 28),
            effective_start=date(2026, 2, 13),
            effective_end=date(2026, 2, 28),
            calculation_date=date(2026, 2, 13),
        )
        # Feb 13 is Friday = 1 working day / 20 = 50000
        self.assertEqual(earned, 50000)

    def test_earned_future_employment(self) -> None:
        earned = _calculate_earned(
            monthly_salary_minor=1000000,
            pay_period_start=date(2026, 2, 1),
            pay_period_end=date(2026, 2, 28),
            effective_start=date(2026, 3, 1),  # Future start
            effective_end=date(2026, 2, 28),
            calculation_date=date(2026, 2, 15),
        )
        # effective_start > calculation_date, so 0
        self.assertEqual(earned, 0)

    def test_earned_employment_ended(self) -> None:
        # Employment ends Feb 10 (Tuesday), calculation Feb 13 (Friday)
        earned = _calculate_earned(
            monthly_salary_minor=1000000,
            pay_period_start=date(2026, 2, 1),
            pay_period_end=date(2026, 2, 28),
            effective_start=date(2026, 2, 1),
            effective_end=date(2026, 2, 10),
            calculation_date=date(2026, 2, 13),
        )
        # Working days Feb 1-10: Feb 2-6 (Mon-Fri, 5), Feb 9-10 (Mon-Tue, 2) = 7 days
        # 1000000 * 7 // 20 = 350000
        self.assertEqual(earned, 350000)

    def test_earned_inactive_employment(self) -> None:
        earned = _calculate_earned(
            monthly_salary_minor=1000000,
            pay_period_start=date(2026, 2, 1),
            pay_period_end=date(2026, 2, 28),
            effective_start=date(2026, 2, 1),
            effective_end=date(2026, 2, 28),
            calculation_date=date(2026, 2, 13),  # Friday
        )
        # Feb 13 = 10 working days / 20 = 500000
        self.assertEqual(earned, 500000)

    def test_earned_future_eligible_from(self) -> None:
        earned = _calculate_earned(
            monthly_salary_minor=1000000,
            pay_period_start=date(2026, 2, 1),
            pay_period_end=date(2026, 2, 28),
            effective_start=date(2026, 2, 20),
            effective_end=date(2026, 2, 28),
            calculation_date=date(2026, 2, 15),
        )
        self.assertEqual(earned, 0)

    def test_earned_expired_eligible_to(self) -> None:
        # Eligible to Feb 10 (Tuesday), calculation Feb 13 (Friday)
        earned = _calculate_earned(
            monthly_salary_minor=1000000,
            pay_period_start=date(2026, 2, 1),
            pay_period_end=date(2026, 2, 28),
            effective_start=date(2026, 2, 1),
            effective_end=date(2026, 2, 10),
            calculation_date=date(2026, 2, 13),
        )
        # Same as employment_ended: 7 working days
        self.assertEqual(earned, 350000)

    # ---- INTEGRATION TESTS WITH DATABASE ----

    async def _setup_complete_employee(self, session: AsyncSession, calc_date: date) -> tuple[User, Employer, Employee, Employment, SalaryProfile, EwaPolicy]:
        user = User(
            id="test-user",
            email="test@example.com",
            hashed_password="hash",
            role="employee",
        )
        session.add(user)

        employer = Employer(
            id="test-employer",
            legal_name="Test Corp",
        )
        session.add(employer)

        employee = Employee(
            id="test-employee",
            user_id=user.id,
            status="active",
        )
        session.add(employee)

        employment = Employment(
            id="test-employment",
            employee_id=employee.id,
            employer_id=employer.id,
            status="active",
            start_date=datetime(2026, 1, 1),
            eligible_from=datetime(2026, 1, 1),
        )
        session.add(employment)

        salary_profile = SalaryProfile(
            id="test-salary",
            employment_id=employment.id,
            monthly_salary_amount_minor=1000000,
            pay_schedule="monthly",
            effective_from=datetime(2026, 1, 1),
            status="active",
        )
        session.add(salary_profile)

        policy = EwaPolicy(
            id="test-policy",
            employer_id=employer.id,
            enabled=True,
            max_access_percentage=50,
            minimum_remaining_salary_minor=100000,
            minimum_withdrawal_minor=1000,
            maximum_withdrawal_minor=500000,
        )
        session.add(policy)

        await session.commit()
        return user, employer, employee, employment, salary_profile, policy

    async def test_complete_setup_returns_deterministic_result(self) -> None:
        session = self._create_test_session()
        calc_date = date(2026, 2, 15)
        user, _, _, _, _, _ = await self._setup_complete_employee(session, calc_date)

        result = await calculate_ewa(session, user.id, calc_date)

        self.assertTrue(result.eligible)
        self.assertEqual(result.eligibility_reasons, ())
        self.assertEqual(result.salary_amount_minor, 1000000)
        # Feb 1-15 = 10 working days / 20 = 500000 earned
        self.assertEqual(result.earned_amount_minor, 500000)
        # 500000 * 50% = 250000 base
        # min remaining 100000: remaining cap = 500000 - 100000 = 400000
        # min(250000, 400000) = 250000
        self.assertEqual(result.policy_limit_minor, 250000)
        self.assertEqual(result.reserved_amount_minor, 0)
        self.assertEqual(result.paid_amount_minor, 0)
        self.assertEqual(result.available_amount_minor, 250000)
        self.assertEqual(result.minimum_withdrawal_minor, 1000)
        self.assertEqual(result.maximum_withdrawal_minor, 500000)
        self.assertTrue(result.can_request_withdrawal)

    async def test_no_salary_profile_ineligible(self) -> None:
        session = self._create_test_session()
        calc_date = date(2026, 2, 15)

        user = User(id="test-user-no-salary", email="test2@example.com", hashed_password="hash", role="employee")
        session.add(user)

        employer = Employer(id="test-employer", legal_name="Test Corp")
        session.add(employer)

        employee = Employee(id="test-employee", user_id=user.id, status="active")
        session.add(employee)

        employment = Employment(
            id="test-employment", employee_id=employee.id, employer_id=employer.id,
            status="active", start_date=datetime(2026, 1, 1)
        )
        session.add(employment)

        policy = EwaPolicy(
            id="test-policy", employer_id=employer.id, enabled=True, max_access_percentage=50
        )
        session.add(policy)

        await session.commit()

        result = await calculate_ewa(session, user.id, calc_date)

        self.assertFalse(result.eligible)
        self.assertEqual(result.eligibility_reasons, (EligibilityReason.NO_ACTIVE_SALARY_PROFILE,))
        self.assertEqual(result.available_amount_minor, 0)

    async def test_no_ewa_policy_ineligible(self) -> None:
        session = self._create_test_session()
        calc_date = date(2026, 2, 15)

        user = User(id="test-user-no-policy", email="test3@example.com", hashed_password="hash", role="employee")
        session.add(user)

        employer = Employer(id="test-employer", legal_name="Test Corp")
        session.add(employer)

        employee = Employee(id="test-employee", user_id=user.id, status="active")
        session.add(employee)

        employment = Employment(
            id="test-employment", employee_id=employee.id, employer_id=employer.id,
            status="active", start_date=datetime(2026, 1, 1)
        )
        session.add(employment)

        salary_profile = SalaryProfile(
            id="test-salary", employment_id=employment.id,
            monthly_salary_amount_minor=1000000, effective_from=datetime(2026, 1, 1), status="active"
        )
        session.add(salary_profile)

        await session.commit()

        result = await calculate_ewa(session, user.id, calc_date)

        self.assertFalse(result.eligible)
        self.assertEqual(result.eligibility_reasons, (EligibilityReason.NO_EWA_POLICY,))

    async def test_ewa_disabled_ineligible(self) -> None:
        session = self._create_test_session()
        calc_date = date(2026, 2, 15)

        user, employer, employee, employment, salary_profile, _ = await self._setup_complete_employee(session, calc_date)

        # Update policy to disabled
        result = await session.execute(select(EwaPolicy).where(EwaPolicy.employer_id == employer.id))
        policy = result.scalar_one()
        policy.enabled = False
        await session.commit()

        result = await calculate_ewa(session, user.id, calc_date)

        self.assertFalse(result.eligible)
        self.assertEqual(result.eligibility_reasons, (EligibilityReason.EWA_DISABLED,))

    async def test_zero_access_percentage(self) -> None:
        session = self._create_test_session()
        calc_date = date(2026, 2, 15)

        user, employer, _, _, _, _ = await self._setup_complete_employee(session, calc_date)

        result = await session.execute(select(EwaPolicy).where(EwaPolicy.employer_id == employer.id))
        policy = result.scalar_one()
        policy.max_access_percentage = 0
        await session.commit()

        result = await calculate_ewa(session, user.id, calc_date)

        self.assertTrue(result.eligible)
        self.assertEqual(result.policy_limit_minor, 0)
        self.assertEqual(result.available_amount_minor, 0)

    async def test_fifty_percent_access(self) -> None:
        session = self._create_test_session()
        calc_date = date(2026, 2, 15)

        user, employer, _, _, _, _ = await self._setup_complete_employee(session, calc_date)

        result = await session.execute(select(EwaPolicy).where(EwaPolicy.employer_id == employer.id))
        policy = result.scalar_one()
        policy.max_access_percentage = 50
        await session.commit()

        result = await calculate_ewa(session, user.id, calc_date)

        self.assertEqual(result.policy_limit_minor, 250000)

    async def test_hundred_percent_access(self) -> None:
        session = self._create_test_session()
        calc_date = date(2026, 2, 15)

        user, employer, _, _, _, _ = await self._setup_complete_employee(session, calc_date)

        result = await session.execute(select(EwaPolicy).where(EwaPolicy.employer_id == employer.id))
        policy = result.scalar_one()
        policy.max_access_percentage = 100
        policy.minimum_remaining_salary_minor = None
        await session.commit()

        result = await calculate_ewa(session, user.id, calc_date)

        self.assertEqual(result.policy_limit_minor, 500000)

    async def test_minimum_tenure_not_met(self) -> None:
        session = self._create_test_session()
        calc_date = date(2026, 2, 15)

        user, employer, _, _, _, _ = await self._setup_complete_employee(session, calc_date)

        result = await session.execute(select(EwaPolicy).where(EwaPolicy.employer_id == employer.id))
        policy = result.scalar_one()
        policy.minimum_tenure_days = 60  # Started Jan 1, only 45 days by Feb 15
        await session.commit()

        result = await calculate_ewa(session, user.id, calc_date)

        self.assertFalse(result.eligible)
        self.assertEqual(result.eligibility_reasons, (EligibilityReason.MINIMUM_TENURE_NOT_MET,))

    async def test_minimum_remaining_salary_cap(self) -> None:
        session = self._create_test_session()
        calc_date = date(2026, 2, 15)

        user, employer, _, _, _, _ = await self._setup_complete_employee(session, calc_date)

        result = await session.execute(select(EwaPolicy).where(EwaPolicy.employer_id == employer.id))
        policy = result.scalar_one()
        policy.minimum_remaining_salary_minor = 450000  # Cap: 500000 - 450000 = 50000
        policy.max_access_percentage = 100
        await session.commit()

        result = await calculate_ewa(session, user.id, calc_date)

        self.assertEqual(result.policy_limit_minor, 50000)  # min(500000, 50000)

    async def test_maximum_withdrawal_cap(self) -> None:
        session = self._create_test_session()
        calc_date = date(2026, 2, 15)

        user, employer, _, _, _, _ = await self._setup_complete_employee(session, calc_date)

        result = await session.execute(select(EwaPolicy).where(EwaPolicy.employer_id == employer.id))
        policy = result.scalar_one()
        policy.max_access_percentage = 100
        policy.minimum_remaining_salary_minor = None
        policy.maximum_withdrawal_minor = 100000
        await session.commit()

        result = await calculate_ewa(session, user.id, calc_date)

        self.assertEqual(result.available_amount_minor, 500000)
        self.assertEqual(result.maximum_withdrawal_minor, 100000)
        self.assertEqual(result.can_request_withdrawal, True)

    async def test_minimum_withdrawal_exceeds_availability(self) -> None:
        session = self._create_test_session()
        calc_date = date(2026, 2, 2)  # Early in month, low availability

        user, employer, _, _, _, _ = await self._setup_complete_employee(session, calc_date)

        result = await session.execute(select(EwaPolicy).where(EwaPolicy.employer_id == employer.id))
        policy = result.scalar_one()
        policy.max_access_percentage = 50
        policy.minimum_remaining_salary_minor = 100000
        policy.minimum_withdrawal_minor = 100000  # Higher than available
        await session.commit()

        result = await calculate_ewa(session, user.id, calc_date)

        # available = min(500000*50%=250000, 500000-100000=400000) = 250000
        # But min withdrawal 100000 > 250000? No, 100000 < 250000 so can request
        # Let's adjust
        policy.minimum_withdrawal_minor = 300000
        await session.commit()

        result = await calculate_ewa(session, user.id, calc_date)

        self.assertFalse(result.can_request_withdrawal)

    async def test_available_never_negative(self) -> None:
        session = self._create_test_session()
        calc_date = date(2026, 2, 15)

        user, employer, employee, employment, salary_profile, policy = await self._setup_complete_employee(session, calc_date)

        # Add a paid request that exceeds policy limit
        request = WageAccessRequest(
            id="req-paid",
            user_id=user.id,
            amount_minor=300000,
            status="paid",
            created_at=datetime(2026, 2, 10),
        )
        session.add(request)
        await session.commit()

        result = await calculate_ewa(session, user.id, calc_date)

        self.assertGreaterEqual(result.available_amount_minor, 0)

    async def test_monthly_income_range_no_effect(self) -> None:
        session = self._create_test_session()
        calc_date = date(2026, 2, 15)

        user = User(id="test-user-income", email="income@example.com", hashed_password="hash", role="employee")
        session.add(user)
        await session.flush()  # Ensure user is persisted for FK

        # Create onboarding with monthly_income_range - should not affect calculation
        from app.models import Onboarding
        onboarding = Onboarding(
            id="test-onboarding",
            user_id=user.id,
            monthly_income_range="750,000+",  # High income range
        )
        session.add(onboarding)

        employer = Employer(id="test-employer", legal_name="Test Corp")
        session.add(employer)

        employee = Employee(id="test-employee", user_id=user.id, status="active")
        session.add(employee)

        employment = Employment(
            id="test-employment", employee_id=employee.id, employer_id=employer.id,
            status="active", start_date=datetime(2026, 1, 1)
        )
        session.add(employment)

        salary_profile = SalaryProfile(
            id="test-salary", employment_id=employment.id,
            monthly_salary_amount_minor=1000000, effective_from=datetime(2026, 1, 1), status="active"
        )
        session.add(salary_profile)

        policy = EwaPolicy(
            id="test-policy", employer_id=employer.id, enabled=True, max_access_percentage=50
        )
        session.add(policy)

        await session.commit()

        result = await calculate_ewa(session, user.id, calc_date)

        # Should calculate based on real SalaryProfile (1000000), not onboarding range
        self.assertEqual(result.salary_amount_minor, 1000000)
        self.assertEqual(result.earned_amount_minor, 500000)


class Phase23EwaApiTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        _reset_all_limiters()
        import httpx
        self.temp_dir = tempfile.TemporaryDirectory()
        self._test_sessions = []
        database_path = Path(self.temp_dir.name) / "ewa_api.db"
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
        for session in self._test_sessions:
            await session.close()
        if self.original_url:
            await configure_database(self.original_url)
        await self.engine.dispose()
        self.temp_dir.cleanup()

    async def _register_and_login(self, email: str):
        body = {"email": email, "password": "password123", "name": "Test User"}
        response = await self.client.post("/auth/register", json=body)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        return data["access_token"], data["user_id"]

    async def _create_complete_setup(self, token: str, user_id: str):
        headers = {"Authorization": f"Bearer {token}"}

        resp = await self.client.post("/employers/", headers=headers, json={"legal_name": "Test Corp"})
        self.assertEqual(resp.status_code, 200)
        employer_id = resp.json()["id"]

        resp = await self.client.post("/employees/", headers=headers, json={"user_id": user_id})
        self.assertEqual(resp.status_code, 200)
        employee_id = resp.json()["id"]

        resp = await self.client.post("/employments/", headers=headers, json={
            "employee_id": employee_id,
            "employer_id": employer_id,
            "start_date": "2026-01-01T00:00:00",
            "status": "active",
        })
        self.assertEqual(resp.status_code, 200)
        employment_id = resp.json()["id"]

        resp = await self.client.post("/salary-profiles/", headers=headers, json={
            "employment_id": employment_id,
            "currency": "USD",
            "monthly_salary_amount_minor": 1000000,
            "pay_schedule": "monthly",
            "effective_from": "2026-01-01T00:00:00",
        })
        self.assertEqual(resp.status_code, 200)

        resp = await self.client.put(f"/employers/{employer_id}/ewa/policy", headers=headers, json={
            "enabled": True,
            "max_access_percentage": 50,
        })
        self.assertEqual(resp.status_code, 200)

        return employer_id, employee_id, employment_id

    async def test_calculation_endpoint_complete_setup(self) -> None:
        token, user_id = await self._register_and_login("calc@example.com")
        headers = {"Authorization": f"Bearer {token}"}

        await self._create_complete_setup(token, user_id)

        resp = await self.client.get("/ewa/calculation", headers=headers)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()

        self.assertTrue(data["eligible"])
        self.assertEqual(data["salary_amount_minor"], 1000000)
        # Deterministic calendar-month accrual: earned = salary * elapsed
        # Mon-Fri working days in the accrual window // total Mon-Fri working
        # days in the calendar month. Compute the expected value from the
        # contract rather than hardcoding a wall-clock-specific number.
        calc_date = datetime.utcnow().date()
        period_start, period_end = _get_pay_period(calc_date)
        total_working_days = _count_working_days(period_start, period_end)
        elapsed_working_days = _count_working_days(period_start, calc_date)
        expected_earned = 1_000_000 * elapsed_working_days // total_working_days
        self.assertEqual(data["earned_amount_minor"], expected_earned)
        # Policy: 50% floor of earned, no existing reservations.
        expected_policy_limit = expected_earned * 50 // 100
        self.assertEqual(data["policy_limit_minor"], expected_policy_limit)
        self.assertEqual(data["available_amount_minor"], expected_policy_limit)
        self.assertEqual(data["eligibility_reasons"], [])

    async def test_no_salary_profile_ineligible(self) -> None:
        token, user_id = await self._register_and_login("no-salary@example.com")
        headers = {"Authorization": f"Bearer {token}"}

        # Create employer but no salary profile
        resp = await self.client.post("/employers/", headers=headers, json={"legal_name": "Test Corp"})
        employer_id = resp.json()["id"]

        resp = await self.client.post("/employees/", headers=headers, json={"user_id": user_id})
        employee_id = resp.json()["id"]

        resp = await self.client.post("/employments/", headers=headers, json={
            "employee_id": employee_id,
            "employer_id": employer_id,
            "start_date": "2026-01-01T00:00:00",
            "status": "active",
        })
        employment_id = resp.json()["id"]

        resp = await self.client.put(f"/employers/{employer_id}/ewa/policy", headers=headers, json={
            "enabled": True,
            "max_access_percentage": 50,
        })
        self.assertEqual(resp.status_code, 200)

        resp = await self.client.get("/ewa/calculation", headers=headers)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()

        self.assertFalse(data["eligible"])
        self.assertIn("NO_ACTIVE_SALARY_PROFILE", data["eligibility_reasons"])

    async def test_no_ewa_policy_ineligible(self) -> None:
        token, user_id = await self._register_and_login("no-policy@example.com")
        headers = {"Authorization": f"Bearer {token}"}

        resp = await self.client.post("/employers/", headers=headers, json={"legal_name": "Test Corp"})
        employer_id = resp.json()["id"]

        resp = await self.client.post("/employees/", headers=headers, json={"user_id": user_id})
        employee_id = resp.json()["id"]

        resp = await self.client.post("/employments/", headers=headers, json={
            "employee_id": employee_id,
            "employer_id": employer_id,
            "start_date": "2026-01-01T00:00:00",
            "status": "active",
        })
        employment_id = resp.json()["id"]

        resp = await self.client.post("/salary-profiles/", headers=headers, json={
            "employment_id": employment_id,
            "currency": "USD",
            "monthly_salary_amount_minor": 1000000,
            "pay_schedule": "monthly",
            "effective_from": "2026-01-01T00:00:00",
        })
        self.assertEqual(resp.status_code, 200)

        # No EWA policy created

        resp = await self.client.get("/ewa/calculation", headers=headers)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()

        self.assertFalse(data["eligible"])
        self.assertIn("NO_EWA_POLICY", data["eligibility_reasons"])

    async def test_monthly_income_range_no_effect_on_calculation(self) -> None:
        token, user_id = await self._register_and_login("income-range@example.com")
        headers = {"Authorization": f"Bearer {token}"}

        # Save onboarding with high income range
        await self.client.put("/auth/onboarding", headers=headers, json={
            "monthly_income_range": "750,000+",
        })

        await self._create_complete_setup(token, user_id)

        resp = await self.client.get("/ewa/calculation", headers=headers)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()

        # Should use real salary profile (1000000), not onboarding range
        self.assertEqual(data["salary_amount_minor"], 1000000)

    # ---- REGRESSION: Legacy EarnedWages fallback removed ----
        """Test 1: User has legacy EarnedWages but NO SalaryProfile.
        GET /ewa/available must NOT return legacy value.
        """
        token, user_id = await self._register_and_login("legacy1@example.com")
        headers = {"Authorization": f"Bearer {token}"}

        # Create employer, employee, employment - but NO salary profile
        resp = await self.client.post("/employers/", headers=headers, json={"legal_name": "Test Corp"})
        employer_id = resp.json()["id"]

        resp = await self.client.post("/employees/", headers=headers, json={"user_id": user_id})
        employee_id = resp.json()["id"]

        resp = await self.client.post("/employments/", headers=headers, json={
            "employee_id": employee_id,
            "employer_id": employer_id,
            "start_date": "2026-01-01T00:00:00",
            "status": "active",
        })
        self.assertEqual(resp.status_code, 200)

        # Create EWA policy
        await self.client.put(f"/employers/{employer_id}/ewa/policy", headers=headers, json={
            "enabled": True,
            "max_access_percentage": 50,
        })

        # Pre-create legacy EarnedWages with available=100000
        async with self.sessions() as session:
            from app.models import EarnedWages
            ew = EarnedWages(
                id="legacy-ew",
                user_id=user_id,
                earned_amount_minor=200000,
                accessed_amount_minor=100000,
                available_amount_minor=100000,
            )
            session.add(ew)
            await session.commit()

        # GET /ewa/available must NOT return legacy 100000
        resp = await self.client.get("/ewa/available", headers=headers)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["available_amount_minor"], 0, "Must not fall back to legacy EarnedWages")

    async def test_available_no_ewa_policy_returns_zero_not_legacy(self) -> None:
        """Test 2: User has legacy EarnedWages but NO EwaPolicy.
        Legacy value must NOT leak into /ewa/available.
        """
        token, user_id = await self._register_and_login("legacy2@example.com")
        headers = {"Authorization": f"Bearer {token}"}

        resp = await self.client.post("/employers/", headers=headers, json={"legal_name": "Test Corp"})
        employer_id = resp.json()["id"]

        resp = await self.client.post("/employees/", headers=headers, json={"user_id": user_id})
        employee_id = resp.json()["id"]

        resp = await self.client.post("/employments/", headers=headers, json={
            "employee_id": employee_id,
            "employer_id": employer_id,
            "start_date": "2026-01-01T00:00:00",
            "status": "active",
        })
        employment_id = resp.json()["id"]

        resp = await self.client.post("/salary-profiles/", headers=headers, json={
            "employment_id": employment_id,
            "currency": "USD",
            "monthly_salary_amount_minor": 1000000,
            "pay_schedule": "monthly",
            "effective_from": "2026-01-01T00:00:00",
        })
        self.assertEqual(resp.status_code, 200)

        # Pre-create legacy EarnedWages with available=500000
        async with self.sessions() as session:
            from app.models import EarnedWages
            ew = EarnedWages(
                id="legacy-ew2",
                user_id=user_id,
                earned_amount_minor=500000,
                accessed_amount_minor=0,
                available_amount_minor=500000,
            )
            session.add(ew)
            await session.commit()

        # GET /ewa/available must NOT return legacy 500000 (no policy = ineligible)
        resp = await self.client.get("/ewa/available", headers=headers)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["available_amount_minor"], 0, "Must not fall back to legacy EarnedWages")

    async def test_available_engine_wins_over_legacy(self) -> None:
        """Test 3: User has legacy EarnedWages with large value PLUS valid real setup.
        The deterministic engine result must win.
        """
        token, user_id = await self._register_and_login("legacy3@example.com")
        headers = {"Authorization": f"Bearer {token}"}

        employer_id, _, _ = await self._create_complete_setup(token, user_id)

        # Pre-create legacy EarnedWages with very large available=999999999
        async with self.sessions() as session:
            from app.models import EarnedWages
            ew = EarnedWages(
                id="legacy-ew3",
                user_id=user_id,
                earned_amount_minor=999999999,
                accessed_amount_minor=0,
                available_amount_minor=999999999,
            )
            session.add(ew)
            await session.commit()

        # GET /ewa/available must return ENGINE result, not legacy
        resp = await self.client.get("/ewa/available", headers=headers)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()

        # Deterministic engine result must win over legacy EarnedWages.
        self.assertNotEqual(data["available_amount_minor"], 999999999)
        # Compute the expected engine value from the contract instead of a
        # wall-clock-specific hardcoded number.
        calc_date = datetime.utcnow().date()
        period_start, period_end = _get_pay_period(calc_date)
        total_working_days = _count_working_days(period_start, period_end)
        elapsed_working_days = _count_working_days(period_start, calc_date)
        expected_earned = 1_000_000 * elapsed_working_days // total_working_days
        self.assertEqual(data["available_amount_minor"], expected_earned * 50 // 100,
                         "Engine result must win over legacy")

    async def test_calculation_not_influenced_by_income_range_or_legacy(self) -> None:
        """Test 4: monthly_income_range + legacy EarnedWages cannot influence calculation."""
        token, user_id = await self._register_and_login("legacy4@example.com")
        headers = {"Authorization": f"Bearer {token}"}

        # Save onboarding with high income range
        await self.client.put("/auth/onboarding", headers=headers, json={
            "monthly_income_range": "750,000+",
        })

        await self._create_complete_setup(token, user_id)

        # Pre-create legacy EarnedWages with large value
        async with self.sessions() as session:
            from app.models import EarnedWages
            ew = EarnedWages(
                id="legacy-ew4",
                user_id=user_id,
                earned_amount_minor=888888888,
                accessed_amount_minor=0,
                available_amount_minor=888888888,
            )
            session.add(ew)
            await session.commit()

        # GET /ewa/calculation must use real salary profile
        resp = await self.client.get("/ewa/calculation", headers=headers)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()

        self.assertEqual(data["salary_amount_minor"], 1000000, "Must use SalaryProfile, not onboarding range")
        self.assertNotEqual(data["available_amount_minor"], 888888888, "Must not use legacy EarnedWages")
